#!/usr/bin/env python3
"""crypto-rebalance: bring a spot crypto portfolio back to its target weights.

Reads:
  crypto/spot.json     {"holdings": {"BTC": 0.05, "ETH": 1.2}, "cash_usdt": 150}
  crypto/prices.json   {"BTC": 97000, "ETH": 3400}
  crypto/targets.json  {"BTC": 50, "ETH": 30, "USDT": 20}    (percent, USDT = cash)

  python3 rebalance.py                 # drift table + proposed trades
  python3 rebalance.py --band 5 --min-trade 20 --json

Only coins that drifted more than --band percentage points are traded,
sells are listed before buys, and nothing is placed: you place the trades.
"""
import argparse
import json
import os
import sys

D = "crypto"


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def rebalance(spot, prices, targets, band=5.0, min_trade=10.0, fee_pct=0.1):
    holdings = {k.upper(): float(v) for k, v in spot.get("holdings", {}).items()}
    cash = float(spot.get("cash_usdt", 0))
    targets = {k.upper(): float(v) for k, v in targets.items()}
    tsum = sum(targets.values())
    if abs(tsum - 100) > 0.01:
        targets = {k: v * 100 / tsum for k, v in targets.items()}
    coins = sorted(set(holdings) | {k for k in targets if k != "USDT"})
    missing = [c for c in coins if c not in prices]
    if missing:
        raise ValueError("no price for: " + ", ".join(missing))
    values = {c: holdings.get(c, 0) * prices[c] for c in coins}
    total = sum(values.values()) + cash
    rows, trades = [], []
    for c in coins + ["USDT"]:
        v = cash if c == "USDT" else values[c]
        w = v / total * 100 if total else 0
        tgt = targets.get(c, 0.0)
        drift = w - tgt
        rows.append({"asset": c, "value_usd": round(v, 2), "weight_pct": round(w, 2),
                     "target_pct": round(tgt, 2), "drift_pts": round(drift, 2),
                     "outside_band": abs(drift) > band})
        if c != "USDT" and abs(drift) > band:
            usd = (tgt - w) / 100 * total
            if abs(usd) >= min_trade:
                trades.append({"side": "buy" if usd > 0 else "sell", "asset": c, "usd": round(abs(usd), 2),
                               "qty": round(abs(usd) / prices[c], 8), "price": prices[c]})
    trades.sort(key=lambda t: (t["side"] != "sell", -t["usd"]))
    cash_after = cash + sum(t["usd"] * (1 - fee_pct / 100) for t in trades if t["side"] == "sell") \
        - sum(t["usd"] * (1 + fee_pct / 100) for t in trades if t["side"] == "buy")
    return {"total_usd": round(total, 2), "rows": rows, "trades": trades,
            "cash_after_usd": round(cash_after, 2), "cash_short": cash_after < -0.01}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--spot", default=os.path.join(D, "spot.json"))
    p.add_argument("--prices", default=os.path.join(D, "prices.json"))
    p.add_argument("--targets", default=os.path.join(D, "targets.json"))
    p.add_argument("--band", type=float, default=5.0)
    p.add_argument("--min-trade", type=float, default=10.0)
    p.add_argument("--fee-pct", type=float, default=0.1)
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    try:
        r = rebalance(load(a.spot), load(a.prices), load(a.targets), a.band, a.min_trade, a.fee_pct)
    except (OSError, ValueError) as e:
        print("Error: {}".format(e), file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(r, indent=2))
        return 0
    print("Portfolio ${:,.2f}   band {} pts".format(r["total_usd"], a.band))
    print("{:<6} {:>12} {:>8} {:>8} {:>8}".format("asset", "value", "now %", "target", "drift"))
    for row in r["rows"]:
        print("{:<6} {:>12,.2f} {:>8.2f} {:>8.2f} {:>+8.2f}{}".format(
            row["asset"], row["value_usd"], row["weight_pct"], row["target_pct"], row["drift_pts"],
            "  <- rebalance" if row["outside_band"] and row["asset"] != "USDT" else ""))
    if not r["trades"]:
        print("Nothing outside the band. No trades.")
    for t in r["trades"]:
        print("{} {} ${:,.2f} (~{} at {})".format(t["side"].upper(), t["asset"], t["usd"], t["qty"], t["price"]))
    if r["cash_short"]:
        print("WARNING: not enough USDT after fees for every buy. Trim the buys.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
