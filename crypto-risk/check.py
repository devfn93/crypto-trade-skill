#!/usr/bin/env python3
"""crypto-risk: checks every planned trade against your rules before you place it.

Reads crypto/plan.json (the planned trades), crypto/config.json (the rules)
and crypto/journal.json (what is already open and what happened today), and
prints PASS or BLOCK for each trade with the reason, plus a ticket you can
type into your exchange for each PASS.

  python3 check.py
  python3 check.py --plan crypto/plan.json --json
  python3 check.py --no-write        # look without recording verdicts

Exit code 0: every trade passed. 1: at least one was blocked.
Standard library only. It never places an order: you do that yourself.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import sys

CONFIG = os.path.join("crypto", "config.json")
JOURNAL = os.path.join("crypto", "journal.json")
PLAN = os.path.join("crypto", "plan.json")
STATE = os.path.join("crypto", "state", "risk.json")

# ---- ledger (same code in crypto-prop/prop.py, kept self-contained) ----

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


def liquidation_price(side, entry, leverage, mmr_pct):
    if not leverage or leverage <= 1:
        return None
    mmr = mmr_pct / 100.0
    if side == "long":
        return entry * (1 - 1.0 / leverage + mmr)
    return entry * (1 + 1.0 / leverage - mmr)


def fingerprint(o):
    keys = ("symbol", "side", "entry", "stop", "qty", "leverage", "type")
    raw = json.dumps({k: o.get(k) for k in keys}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def check_orders(cfg, journal, orders, now):
    fee = cfg.get("taker_fee_pct", 0.05)
    mmr = cfg.get("maintenance_margin_pct", 0.5)
    # work on a copy so passed orders count against later ones in the batch
    sim = {"trades": [dict(t) for t in journal.get("trades", [])]}
    results = []
    batch_seen = set()
    for i, o in enumerate(orders, 1):
        reasons, warnings = [], []
        o = dict(o)
        s = ledger(cfg, sim, now)
        sym = str(o.get("symbol", "")).upper()
        side = str(o.get("side", "")).lower()
        entry, stop = o.get("entry"), o.get("stop")
        lev = float(o.get("leverage") or cfg.get("default_leverage", 1))
        o.update({"symbol": sym, "side": side, "leverage": lev})

        # format
        if not sym:
            reasons.append("no symbol")
        if side not in ("long", "short"):
            reasons.append("side must be long or short")
        if not isinstance(entry, (int, float)) or entry <= 0:
            reasons.append("entry price missing or not a number")
        if stop is None:
            if cfg.get("stop_loss_required", True):
                reasons.append("no stop loss (your rules require one on every trade)")
        elif not isinstance(stop, (int, float)) or stop <= 0:
            reasons.append("stop is not a valid price")
        elif isinstance(entry, (int, float)) and side in ("long", "short"):
            if side == "long" and stop >= entry:
                reasons.append("long stop must be below entry")
            if side == "short" and stop <= entry:
                reasons.append("short stop must be above entry")
        if reasons:
            results.append({"index": i, "order": o, "verdict": "BLOCK", "reasons": reasons, "warnings": warnings})
            continue

        # size: use the given qty, or size it from risk_per_trade_pct
        risk_budget = s["balance"] * cfg.get("risk_per_trade_pct", 1) / 100.0
        per_unit = abs(entry - stop) + (entry + stop) * fee / 100.0 if stop else None
        if not o.get("qty"):
            if not per_unit:
                reasons.append("no qty and no stop to size from")
            else:
                o["qty"] = round(min(risk_budget, max(0.0, s["max_next_risk"])) / per_unit, 8)
                o["sized_by"] = "risk_per_trade_pct (capped by daily/drawdown room)"
                if o["qty"] <= 0:
                    reasons.append("no risk room left today to size a trade")
        qty = float(o.get("qty") or 0)
        risk = qty * per_unit if per_unit else None
        notional = qty * entry
        margin = notional / lev
        o["risk_usd"] = round(risk, 2) if risk is not None else None
        o["notional_usd"] = round(notional, 2)
        o["margin_usd"] = round(margin, 2)

        # asset
        allowed = [x.upper() for x in cfg.get("allowed_symbols", [])]
        if sym in [x.upper() for x in cfg.get("blocked_symbols", [])]:
            reasons.append("{} is on your blocked list".format(sym))
        if allowed and sym not in allowed:
            reasons.append("{} is not on your allowed list".format(sym))
        if side == "short" and not cfg.get("allow_short", True):
            reasons.append("short trades are off in your rules")

        # leverage and liquidation
        if lev > cfg.get("max_leverage", 1):
            reasons.append("leverage {}x is over your max {}x".format(lev, cfg.get("max_leverage", 1)))
        liq = liquidation_price(side, entry, lev, mmr)
        o["liquidation_est"] = round(liq, 8) if liq else None
        if liq and stop and ((side == "long" and stop <= liq) or (side == "short" and stop >= liq)):
            reasons.append("liquidation (~{:.6g}) comes before your stop: lower the leverage".format(liq))

        # per-trade risk
        max_risk = s["balance"] * cfg.get("max_risk_per_trade_pct", cfg.get("risk_per_trade_pct", 1)) / 100.0
        if risk is not None and risk > max_risk * 1.01:
            reasons.append("risk ${:,.2f} is over your max per trade ${:,.2f}".format(risk, max_risk))
        if cfg.get("max_notional_usd") and notional > cfg["max_notional_usd"]:
            reasons.append("size ${:,.0f} is over your max position ${:,.0f}".format(notional, cfg["max_notional_usd"]))

        # reward to risk
        targets = o.get("targets") or []
        min_rr = cfg.get("min_rr")
        if targets and risk:
            t1 = targets[0]
            gain = ((t1 - entry) if side == "long" else (entry - t1)) * qty - qty * (entry + t1) * fee / 100.0
            rr = gain / risk
            o["rr_first_target"] = round(rr, 2)
            if gain <= 0:
                reasons.append("first target is on the wrong side of the entry")
            elif min_rr and rr < min_rr:
                reasons.append("reward:risk {:.2f} is under your minimum {}".format(rr, min_rr))
        elif min_rr:
            warnings.append("no target given, reward:risk not checked")

        # account-level limits
        if margin + s["open_margin"] > s["balance"]:
            reasons.append("margin ${:,.2f} plus open margin ${:,.2f} is more than the balance".format(margin, s["open_margin"]))
        if s["open_positions"] >= cfg.get("max_open_positions", 99):
            reasons.append("already {} open positions (max {})".format(s["open_positions"], cfg.get("max_open_positions")))
        if cfg.get("max_total_open_risk_pct") and risk is not None:
            cap = s["balance"] * cfg["max_total_open_risk_pct"] / 100.0
            if s["open_risk"] + risk > cap * 1.01:
                reasons.append("total open risk would be ${:,.2f}, over your cap ${:,.2f}".format(s["open_risk"] + risk, cap))
        if risk is not None and risk > s["daily_room"]:
            reasons.append("risk ${:,.2f} is more than the daily loss room left ${:,.2f}".format(risk, max(0, s["daily_room"])))
        if risk is not None and risk > s["drawdown_room"]:
            reasons.append("risk ${:,.2f} could break the max drawdown (room ${:,.2f})".format(risk, max(0, s["drawdown_room"])))
        if cfg.get("max_trades_per_day") and s["trades_today"] >= cfg["max_trades_per_day"]:
            reasons.append("already {} trades today (max {})".format(s["trades_today"], cfg["max_trades_per_day"]))
        key = (sym, side)
        if key in batch_seen or any(t["symbol"] == sym and t["side"] == side and t.get("status") == "open"
                                    for t in sim["trades"]):
            reasons.append("same symbol and side already open or planned")
        if s["open_without_stop"]:
            warnings.append("open trade(s) without a stop: #{}".format(", #".join(map(str, s["open_without_stop"]))))
        if not cfg.get("paper", True):
            warnings.append("LIVE account in your config")

        verdict = "BLOCK" if reasons else "PASS"
        o["fingerprint"] = fingerprint(o)
        results.append({"index": i, "order": o, "verdict": verdict, "reasons": reasons, "warnings": warnings})
        if verdict == "PASS":
            batch_seen.add(key)
            sim["trades"].append({"id": -i, "symbol": sym, "side": side, "entry": entry, "stop": stop,
                                  "qty": qty, "leverage": lev, "status": "open",
                                  "opened": now.isoformat()})
    return results


def ticket(r, n, cfg):
    o = r["order"]
    lines = ["TICKET {} of {}  ({} account) - you place this yourself".format(
        r["index"], n, "PAPER/DEMO" if cfg.get("paper", True) else "LIVE"),
        "  {} {} {}  qty {}  ~${:,.2f}".format(o["side"].upper(), o["symbol"], o.get("type", "limit"),
                                              o["qty"], o["notional_usd"]),
        "  entry {}   stop {}   leverage {}x (isolated)".format(o["entry"], o["stop"], o["leverage"])]
    if o.get("targets"):
        lines.append("  targets {}   (R:R to first {})".format(", ".join(map(str, o["targets"])), o.get("rr_first_target")))
    lines.append("  loss at stop ${:,.2f}   margin ${:,.2f}   liquidation ~{}".format(
        o["risk_usd"], o["margin_usd"], o.get("liquidation_est")))
    lines.append("  Set the stop loss on the exchange in the same order, not later.")
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=CONFIG)
    p.add_argument("--journal", default=JOURNAL)
    p.add_argument("--plan", default=PLAN)
    p.add_argument("--state", default=STATE)
    p.add_argument("--now")
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-write", action="store_true")
    a = p.parse_args(argv)
    for path in (a.config, a.plan):
        if not os.path.exists(path):
            print("Missing {}.".format(path), file=sys.stderr)
            return 2
    with open(a.config, encoding="utf-8") as f:
        cfg = json.load(f)
    with open(a.plan, encoding="utf-8") as f:
        plan = json.load(f)
    journal = {"trades": []}
    if os.path.exists(a.journal):
        with open(a.journal, encoding="utf-8") as f:
            journal = json.load(f)
    now = parse_time(a.now) if a.now else dt.datetime.now(dt.timezone.utc)
    orders = plan.get("orders", plan if isinstance(plan, list) else [])
    results = check_orders(cfg, journal, orders, now)
    if not a.no_write:
        os.makedirs(os.path.dirname(a.state) or ".", exist_ok=True)
        with open(a.state, "w", encoding="utf-8") as f:
            json.dump({"checked": now.isoformat(), "results": results}, f, indent=2)
    if a.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            o = r["order"]
            print("{}  #{} {} {}{}".format(r["verdict"], r["index"], o.get("side", "?"), o.get("symbol", "?"),
                                           "  risk ${:,.2f}".format(o["risk_usd"]) if o.get("risk_usd") is not None else ""))
            for why in r["reasons"]:
                print("      - " + why)
            for w in r["warnings"]:
                print("      ! " + w)
        passed = [r for r in results if r["verdict"] == "PASS"]
        print("{} passed, {} blocked.".format(len(passed), len(results) - len(passed)))
        for r in passed:
            print()
            print(ticket(r, len(results), cfg))
    return 0 if all(r["verdict"] == "PASS" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
