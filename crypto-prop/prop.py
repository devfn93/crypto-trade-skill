#!/usr/bin/env python3
"""crypto-prop: where the account stands against prop-firm (challenge) rules.

Reads crypto/config.json (the rules) and crypto/journal.json (the trades)
and prints: balance, today's P&L, daily loss used and left, max drawdown
used and left (static or trailing), profit target progress, trading days,
and how much the next trade can risk without breaking a rule.

  python3 prop.py
  python3 prop.py --json
  python3 prop.py --now 2026-11-13T15:00:00Z      # for testing

Standard library only. Nothing here talks to an exchange. Your firm's own
dashboard is the final word: it may count floating P&L, fees or funding
differently. Check it.
"""
import argparse
import datetime as dt
import json
import os
import sys

CONFIG = os.path.join("crypto", "config.json")
JOURNAL = os.path.join("crypto", "journal.json")


# ---- ledger (same code in crypto-risk/check.py, kept self-contained) ----

def parse_time(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


def day_start(now, reset="00:00"):
    h, m = [int(x) for x in reset.split(":")]
    start = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if now < start:
        start -= dt.timedelta(days=1)
    return start


def trade_pnl(t, fee_pct):
    if t.get("pnl_usd") is not None:
        return t["pnl_usd"]
    q, e, x = t["qty"], t["entry"], t["exit"]
    gross = (x - e) * q if t["side"] == "long" else (e - x) * q
    fees = t.get("fees")
    if fees is None:
        fees = q * (e + x) * fee_pct / 100.0
    return gross - fees - (t.get("funding") or 0)


def risk_at_stop(t, fee_pct):
    q, e, s = t["qty"], t["entry"], t.get("stop")
    if s is None:
        return None
    loss = (e - s) * q if t["side"] == "long" else (s - e) * q
    return loss + q * (e + s) * fee_pct / 100.0


def ledger(cfg, journal, now):
    fee = cfg.get("taker_fee_pct", 0.05)
    initial = float(cfg["account_size"])
    trades = journal.get("trades", [])
    closed = sorted([t for t in trades if t.get("status") == "closed"], key=lambda t: t["closed"])
    opened = [t for t in trades if t.get("status") == "open"]
    start = day_start(now, cfg.get("day_reset_utc", "00:00"))
    balance = hwm = initial
    today = 0.0
    for t in closed:
        p = trade_pnl(t, fee)
        balance += p
        hwm = max(hwm, balance)
        if parse_time(t["closed"]) >= start:
            today += p
    sod = balance - today
    unknown_risk = [t["id"] for t in opened if t.get("stop") is None]
    open_risk = sum(max(0.0, risk_at_stop(t, fee) or 0.0) for t in opened)
    open_margin = sum(t["qty"] * t["entry"] / (t.get("leverage") or 1) for t in opened)
    base = sod if cfg.get("daily_loss_base", "start_of_day") == "start_of_day" else initial
    daily_limit = base * cfg.get("daily_loss_limit_pct", 100) / 100.0
    daily_room = daily_limit + today - open_risk
    dd = cfg.get("max_drawdown_pct", 100) / 100.0
    if cfg.get("drawdown_type", "static") == "trailing":
        floor = hwm * (1 - dd)
        if cfg.get("trailing_locks_at_initial", False):
            floor = min(floor, initial)
    else:
        floor = initial * (1 - dd)
    dd_room = balance - open_risk - floor
    days = sorted({day_start(parse_time(t["opened"]), cfg.get("day_reset_utc", "00:00")).date().isoformat()
                   for t in trades if t.get("opened")})
    target_pct = cfg.get("profit_target_pct")
    trades_today = sum(1 for t in trades if t.get("opened") and parse_time(t["opened"]) >= start)
    return {
        "initial": initial,
        "balance": round(balance, 2),
        "high_water_mark": round(hwm, 2),
        "today_realized": round(today, 2),
        "start_of_day_balance": round(sod, 2),
        "open_positions": len(opened),
        "open_risk": round(open_risk, 2),
        "open_margin": round(open_margin, 2),
        "open_without_stop": unknown_risk,
        "daily_limit": round(daily_limit, 2),
        "daily_room": round(daily_room, 2),
        "drawdown_floor": round(floor, 2),
        "drawdown_room": round(dd_room, 2),
        "trades_today": trades_today,
        "trading_days": len(days),
        "profit_pct": round((balance - initial) / initial * 100, 2),
        "profit_target_pct": target_pct,
        "profit_to_target": round(initial * target_pct / 100.0 - (balance - initial), 2) if target_pct else None,
        "max_next_risk": round(max(0.0, min(daily_room, dd_room)), 2),
    }

# ---- end ledger ----


def render(s, cfg):
    def money(x):
        return ("-" if x < 0 else "") + "${:,.2f}".format(abs(x))
    lines = [
        "Balance          {}  (start {}, {}{}%)".format(money(s["balance"]), money(s["initial"]),
                                                        "+" if s["profit_pct"] >= 0 else "", s["profit_pct"]),
        "Today            {} realized, {} open trade(s) risking {}".format(
            money(s["today_realized"]), s["open_positions"], money(s["open_risk"])),
        "Daily loss       limit {}  ->  room left {}".format(money(s["daily_limit"]), money(s["daily_room"])),
        "Max drawdown     floor {} ({})  ->  room left {}".format(
            money(s["drawdown_floor"]), cfg.get("drawdown_type", "static"), money(s["drawdown_room"])),
    ]
    if s["profit_target_pct"]:
        lines.append("Profit target    {}%  ->  {} to go".format(s["profit_target_pct"], money(max(0, s["profit_to_target"]))))
    if cfg.get("min_trading_days"):
        lines.append("Trading days     {} of {}".format(s["trading_days"], cfg["min_trading_days"]))
    lines.append("Next trade may risk at most {} without breaking a rule".format(money(s["max_next_risk"])))
    if s["open_without_stop"]:
        lines.append("DANGER: open trade(s) without a stop: #{}. Their risk is unknown.".format(
            ", #".join(str(i) for i in s["open_without_stop"])))
    if s["daily_room"] <= 0:
        lines.append("STOP: daily loss room is used up. No new trades until the daily reset.")
    if s["drawdown_room"] <= 0:
        lines.append("STOP: the max drawdown floor is reached or at risk.")
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=CONFIG)
    p.add_argument("--journal", default=JOURNAL)
    p.add_argument("--now")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    if not os.path.exists(a.config):
        print("No {}. Copy config.example.json there and fill in your rules.".format(a.config), file=sys.stderr)
        return 2
    with open(a.config, encoding="utf-8") as f:
        cfg = json.load(f)
    journal = {"trades": []}
    if os.path.exists(a.journal):
        with open(a.journal, encoding="utf-8") as f:
            journal = json.load(f)
    now = parse_time(a.now) if a.now else dt.datetime.now(dt.timezone.utc)
    s = ledger(cfg, journal, now)
    print(json.dumps(s, indent=2) if a.json else render(s, cfg))
    return 0 if s["daily_room"] > 0 and s["drawdown_room"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
