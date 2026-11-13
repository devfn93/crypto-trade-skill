#!/usr/bin/env python3
"""crypto-prop simulate: how likely is this challenge to pass at each risk size?

Runs thousands of random challenges with your own numbers and your firm's
rules (crypto/config.json) and counts how many pass, how many break a rule,
and how many run out of time.

  python3 simulate.py --win-rate 45 --avg-win-r 2 --avg-loss-r 1
  python3 simulate.py --from-journal                  # uses your real R results
  python3 simulate.py --win-rate 40 --avg-win-r 2.2 --risk-pcts 0.5 1 2 --trades-per-day 3 --max-days 30

Two columns are printed for each risk size:
  raw      you take every trade at full size, whatever the room left
  guarded  you never risk more than the daily / drawdown room left
           (what crypto-risk enforces); "stuck" = the account is still alive
           but too close to the drawdown floor to trade a normal size

It assumes every trade is independent and your past numbers hold. Real
trading has streaks, slippage and bad days: read the result as a comparison
between risk sizes, not as a forecast. Standard library only.
"""
import argparse
import json
import os
import random
import sys

CONFIG = os.path.join("crypto", "config.json")
JOURNAL = os.path.join("crypto", "journal.json")


def journal_rs(path, fee_pct):
    with open(path, encoding="utf-8") as f:
        trades = json.load(f).get("trades", [])
    rs = []
    for t in trades:
        if t.get("status") != "closed" or not t.get("initial_risk_usd"):
            continue
        pnl = t.get("pnl_usd")
        if pnl is None:
            q, e, x = t["qty"], t["entry"], t["exit"]
            pnl = ((x - e) if t["side"] == "long" else (e - x)) * q - q * (e + x) * fee_pct / 100.0
        rs.append(pnl / t["initial_risk_usd"])
    return rs


def one_run(rng, draw, cfg, risk_pct, trades_per_day, max_days, guarded):
    initial = float(cfg.get("account_size", 10000))
    target = initial * (1 + cfg.get("profit_target_pct", 10) / 100.0)
    dd = cfg.get("max_drawdown_pct", 10) / 100.0
    trailing = cfg.get("drawdown_type", "static") == "trailing"
    lock = cfg.get("trailing_locks_at_initial", False)
    daily_pct = cfg.get("daily_loss_limit_pct", 5) / 100.0
    base_sod = cfg.get("daily_loss_base", "start_of_day") == "start_of_day"
    min_days = cfg.get("min_trading_days", 0)
    bal = hwm = initial
    for day in range(1, max_days + 1):
        sod, day_pnl = bal, 0.0
        daily_limit = (sod if base_sod else initial) * daily_pct
        for _ in range(trades_per_day):
            floor = hwm * (1 - dd) if trailing else initial * (1 - dd)
            if trailing and lock:
                floor = min(floor, initial)
            risk = bal * risk_pct / 100.0
            if guarded:
                room = min(daily_limit + day_pnl, bal - floor)
                if room < risk * 0.25:
                    if bal - floor < risk * 0.25:
                        return "stalled", day
                    break  # no room left today
                risk = min(risk, room * 0.9)  # keep a margin: touching the limit is a breach
            pnl = draw(rng) * risk
            bal += pnl
            day_pnl += pnl
            hwm = max(hwm, bal)
            floor = hwm * (1 - dd) if trailing else initial * (1 - dd)
            if trailing and lock:
                floor = min(floor, initial)
            if bal <= floor:
                return "bust_drawdown", day
            if -day_pnl >= daily_limit:
                return "bust_daily", day
            if bal >= target and day >= min_days:
                return "pass", day
        if bal >= target and day >= min_days:
            return "pass", day
    return "timeout", max_days


def simulate(cfg, draw, risk_pcts, trades_per_day=2, max_days=30, runs=5000, seed=7):
    out = []
    for rp in risk_pcts:
        row = {"risk_pct": rp}
        for mode, guarded in (("raw", False), ("guarded", True)):
            rng = random.Random(seed)
            counts, days = {}, []
            for _ in range(runs):
                res, d = one_run(rng, draw, cfg, rp, trades_per_day, max_days, guarded)
                counts[res] = counts.get(res, 0) + 1
                if res == "pass":
                    days.append(d)
            days.sort()
            row[mode] = {
                "pass_pct": round(counts.get("pass", 0) / runs * 100, 1),
                "bust_pct": round((counts.get("bust_drawdown", 0) + counts.get("bust_daily", 0)) / runs * 100, 1),
                "stuck_pct": round(counts.get("stalled", 0) / runs * 100, 1),
                "timeout_pct": round(counts.get("timeout", 0) / runs * 100, 1),
                "median_days_to_pass": days[len(days) // 2] if days else None,
            }
        out.append(row)
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=CONFIG)
    p.add_argument("--journal", default=JOURNAL)
    p.add_argument("--from-journal", action="store_true", help="resample your own closed trades (needs 20+)")
    p.add_argument("--win-rate", type=float, help="percent of trades that win")
    p.add_argument("--avg-win-r", type=float, default=2.0)
    p.add_argument("--avg-loss-r", type=float, default=1.0)
    p.add_argument("--risk-pcts", type=float, nargs="+", default=[0.25, 0.5, 1.0, 1.5, 2.0])
    p.add_argument("--trades-per-day", type=int, default=2)
    p.add_argument("--max-days", type=int, default=30)
    p.add_argument("--runs", type=int, default=5000)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    cfg = {}
    if os.path.exists(a.config):
        with open(a.config, encoding="utf-8") as f:
            cfg = json.load(f)
    if a.from_journal:
        if not os.path.exists(a.journal):
            print("No journal at {}.".format(a.journal), file=sys.stderr)
            return 2
        rs = journal_rs(a.journal, cfg.get("taker_fee_pct", 0.05))
        if len(rs) < 20:
            print("Only {} closed trades with a known risk: need 20 or more. "
                  "Use --win-rate / --avg-win-r instead.".format(len(rs)), file=sys.stderr)
            return 2
        draw = lambda rng: rng.choice(rs)
        basis = "{} trades from your journal (avg {:+.2f}R)".format(len(rs), sum(rs) / len(rs))
        edge = sum(rs) / len(rs)
    else:
        if a.win_rate is None:
            p.error("give --win-rate (with --avg-win-r / --avg-loss-r) or --from-journal")
        w, aw, al = a.win_rate / 100.0, a.avg_win_r, a.avg_loss_r
        draw = lambda rng: aw if rng.random() < w else -al
        edge = w * aw - (1 - w) * al
        basis = "win rate {}%, avg win {}R, avg loss {}R (expectancy {:+.2f}R)".format(a.win_rate, aw, al, edge)
    rows = simulate(cfg, draw, a.risk_pcts, a.trades_per_day, a.max_days, a.runs, a.seed)
    if a.json:
        print(json.dumps({"basis": basis, "expectancy_r": round(edge, 3), "rows": rows}, indent=2))
        return 0
    print("Based on: " + basis)
    print("Rules: target {}%, daily loss {}%, max drawdown {}% ({}), {} trades/day, {} days, {} runs".format(
        cfg.get("profit_target_pct", 10), cfg.get("daily_loss_limit_pct", 5), cfg.get("max_drawdown_pct", 10),
        cfg.get("drawdown_type", "static"), a.trades_per_day, a.max_days, a.runs))
    print("{:>6} | {:>24} | {:>24}".format("risk", "raw: pass / bust / time", "guarded: pass / stuck / time"))
    for r in rows:
        f = lambda m: "{:>5.1f}% {:>5.1f}% {:>5.1f}%".format(
            m["pass_pct"], m["bust_pct"] + m["stuck_pct"], m["timeout_pct"])
        print("{:>5}% | {:>24} | {:>24}   median {} days".format(
            r["risk_pct"], f(r["raw"]), f(r["guarded"]), r["guarded"]["median_days_to_pass"]))
    if edge <= 0:
        print("! Expectancy is not above zero: no risk size fixes that. Work on the strategy first.")
    print("! A comparison between risk sizes, not a forecast. Real trading has streaks and slippage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
