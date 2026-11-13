#!/usr/bin/env python3
"""crypto-journal review: where the money is made and lost.

Breaks closed trades down by hour of day, weekday, coin, side, tag and
holding time, and looks at what happens right after a loss.

  python3 review.py
  python3 review.py --tz-offset 3 --min-trades 3
  python3 review.py --json

Hours and weekdays are shown in local time (tz_offset_hours in the config,
or --tz-offset). Small groups prove nothing: groups under --min-trades are
marked. Standard library only.
"""
import argparse
import datetime as dt
import json
import os
import sys

JOURNAL = os.path.join("crypto", "journal.json")
CONFIG = os.path.join("crypto", "config.json")
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def ptime(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


def pnl_of(t, fee_pct):
    if t.get("pnl_usd") is not None:
        return t["pnl_usd"]
    q, e, x = t["qty"], t["entry"], t["exit"]
    gross = (x - e) * q if t["side"] == "long" else (e - x) * q
    fees = t.get("fees")
    if fees is None:
        fees = q * (e + x) * fee_pct / 100.0
    return gross - fees - (t.get("funding") or 0)


def hold_bucket(minutes):
    for limit, name in ((15, "under 15m"), (60, "15m-1h"), (240, "1h-4h"), (1440, "4h-24h")):
        if minutes < limit:
            return name
    return "over 24h"


def group(rows, keyfn):
    g = {}
    for r in rows:
        ks = keyfn(r)
        for k in (ks if isinstance(ks, list) else [ks]):
            g.setdefault(k, []).append(r["pnl"])
    out = {}
    for k, ps in g.items():
        wins = [p for p in ps if p > 0]
        out[k] = {"trades": len(ps), "win_rate_pct": round(len(wins) / len(ps) * 100, 1),
                  "net_usd": round(sum(ps), 2), "avg_usd": round(sum(ps) / len(ps), 2)}
    return out


def review(trades, fee_pct=0.05, tz_offset=0.0, fast_minutes=15):
    tz = dt.timedelta(hours=tz_offset)
    rows = []
    for t in trades:
        if t.get("status") != "closed" or not t.get("closed"):
            continue
        o, c = ptime(t.get("opened") or t["closed"]), ptime(t["closed"])
        rows.append({"t": t, "pnl": pnl_of(t, fee_pct), "opened": o, "closed": c,
                     "local": o + tz, "hold": (c - o).total_seconds() / 60.0})
    rows.sort(key=lambda r: r["opened"])
    after = {"after_a_loss": [], "after_a_win": [], "fast_reentry_after_loss": []}
    by_close = sorted(rows, key=lambda r: r["closed"])
    for r in rows:
        prev = [x for x in by_close if x["closed"] <= r["opened"]]
        if not prev:
            continue
        last = prev[-1]
        if last["pnl"] <= 0:
            after["after_a_loss"].append(r)
            if (r["opened"] - last["closed"]).total_seconds() / 60.0 <= fast_minutes:
                after["fast_reentry_after_loss"].append(r)
        else:
            after["after_a_win"].append(r)
    out = {
        "closed_trades": len(rows),
        "net_usd": round(sum(r["pnl"] for r in rows), 2),
        "by_hour": group(rows, lambda r: "{:02d}:00".format(r["local"].hour)),
        "by_weekday": group(rows, lambda r: DAYS[r["local"].weekday()]),
        "by_symbol": group(rows, lambda r: r["t"]["symbol"]),
        "by_side": group(rows, lambda r: r["t"]["side"]),
        "by_hold_time": group(rows, lambda r: hold_bucket(r["hold"])),
        "by_tag": group([r for r in rows if r["t"].get("tags")], lambda r: list(r["t"]["tags"])),
        "sequence": {k: group(v, lambda r: k).get(k, {"trades": 0}) for k, v in after.items()},
    }
    return out


def findings(rv, min_trades=5):
    f = []
    for name in ("by_hour", "by_weekday", "by_symbol", "by_side", "by_hold_time", "by_tag"):
        big = {k: v for k, v in rv[name].items() if v["trades"] >= min_trades}
        if len(big) >= 2:
            worst = min(big.items(), key=lambda kv: kv[1]["net_usd"])
            best = max(big.items(), key=lambda kv: kv[1]["net_usd"])
            if worst[1]["net_usd"] < 0:
                f.append("{}: '{}' lost ${:,.2f} over {} trades.".format(
                    name[3:], worst[0], -worst[1]["net_usd"], worst[1]["trades"]))
            if best[1]["net_usd"] > 0:
                f.append("{}: '{}' made ${:,.2f} over {} trades.".format(
                    name[3:], best[0], best[1]["net_usd"], best[1]["trades"]))
    s = rv["sequence"]
    al, aw, fr = s["after_a_loss"], s["after_a_win"], s["fast_reentry_after_loss"]
    if al.get("trades", 0) >= min_trades and aw.get("trades", 0) >= min_trades and al["avg_usd"] < aw["avg_usd"]:
        f.append("Trades taken after a loss average ${:,.2f}, after a win ${:,.2f}.".format(al["avg_usd"], aw["avg_usd"]))
    if fr.get("trades", 0) >= 3 and fr["net_usd"] < 0:
        f.append("Quick re-entries after a loss: {} trades, net ${:,.2f}. A cooldown rule would have skipped them.".format(
            fr["trades"], fr["net_usd"]))
    if rv["closed_trades"] < 30:
        f.append("Only {} closed trades: treat every pattern here as a hint, not a fact.".format(rv["closed_trades"]))
    return f


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--journal", default=JOURNAL)
    p.add_argument("--config", default=CONFIG)
    p.add_argument("--tz-offset", type=float)
    p.add_argument("--min-trades", type=int, default=5)
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    if not os.path.exists(a.journal):
        print("No journal at {}.".format(a.journal), file=sys.stderr)
        return 2
    cfg = {}
    if os.path.exists(a.config):
        with open(a.config, encoding="utf-8") as f:
            cfg = json.load(f)
    with open(a.journal, encoding="utf-8") as f:
        trades = json.load(f).get("trades", [])
    tz = a.tz_offset if a.tz_offset is not None else cfg.get("tz_offset_hours", 0)
    rv = review(trades, cfg.get("taker_fee_pct", 0.05), tz)
    notes = findings(rv, a.min_trades)
    if a.json:
        print(json.dumps({"review": rv, "findings": notes}, indent=2))
        return 0
    print("{} closed trades, net ${:,.2f}  (local time = UTC{:+g})".format(rv["closed_trades"], rv["net_usd"], tz))
    for name in ("by_symbol", "by_side", "by_weekday", "by_hour", "by_hold_time", "by_tag"):
        if not rv[name]:
            continue
        print("\n" + name.replace("_", " "))
        order = DAYS if name == "by_weekday" else sorted(rv[name])
        for k in order:
            v = rv[name].get(k)
            if v:
                print("  {:<12} {:>3} trades  win {:>5.1f}%  net {:>10,.2f}  avg {:>8,.2f}{}".format(
                    k, v["trades"], v["win_rate_pct"], v["net_usd"], v["avg_usd"],
                    "" if v["trades"] >= a.min_trades else "   (few)"))
    print("\nsequence")
    for k, v in rv["sequence"].items():
        if v.get("trades"):
            print("  {:<26} {:>3} trades  win {:>5.1f}%  net {:>10,.2f}  avg {:>8,.2f}".format(
                k.replace("_", " "), v["trades"], v["win_rate_pct"], v["net_usd"], v["avg_usd"]))
    print("\nfindings")
    for n in notes or ["Nothing stands out yet."]:
        print("  - " + n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
