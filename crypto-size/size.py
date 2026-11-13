#!/usr/bin/env python3
"""crypto-size: position size for a USDT-margined (linear) perpetual or spot trade.

Sizes a trade from the money you are willing to lose if the stop is hit,
fees included, then shows the margin, the leverage it really needs and an
estimate of the liquidation price (isolated margin).

Standard library only. Nothing here talks to an exchange.

Examples:
  python3 size.py --balance 2500 --risk-pct 1 --side short --entry 97000 --stop 98200 --leverage 5
  python3 size.py --side long --entry 3.12 --stop 2.98 --targets 3.40 3.70     # reads crypto/config.json
  python3 size.py ... --json
"""
import argparse
import json
import os
import sys

DEFAULT_CONFIG = os.path.join("crypto", "config.json")


def load_json(path, default=None):
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def liquidation_price(side, entry, leverage, mmr_pct):
    """Isolated-margin estimate for a linear contract (fees and funding ignored).

    long:  entry * (1 - 1/leverage + mmr)
    short: entry * (1 + 1/leverage - mmr)
    Exchanges add tiers and fees, so the real price is a little closer.
    """
    if not leverage or leverage <= 1:
        return None  # 1x long cannot be liquidated; treat as spot-like
    mmr = mmr_pct / 100.0
    if side == "long":
        return entry * (1 - 1.0 / leverage + mmr)
    return entry * (1 + 1.0 / leverage - mmr)


def size_trade(balance, risk_pct, side, entry, stop, leverage=1.0,
               fee_pct=0.05, mmr_pct=0.5, targets=None, risk_usd=None,
               qty_step=None):
    side = side.lower()
    if side not in ("long", "short"):
        raise ValueError("side must be long or short")
    if entry <= 0 or stop <= 0:
        raise ValueError("entry and stop must be above zero")
    if side == "long" and stop >= entry:
        raise ValueError("for a long the stop must be below the entry")
    if side == "short" and stop <= entry:
        raise ValueError("for a short the stop must be above the entry")
    fee = fee_pct / 100.0
    budget = risk_usd if risk_usd is not None else balance * risk_pct / 100.0
    per_unit = abs(entry - stop) + entry * fee + stop * fee
    qty = budget / per_unit
    if qty_step:
        qty = int(qty / qty_step) * qty_step
    notional = qty * entry
    margin = notional / leverage if leverage else notional
    risk_total = qty * per_unit
    liq = liquidation_price(side, entry, leverage, mmr_pct)
    if liq is None:
        stop_before_liq = True
    elif side == "long":
        stop_before_liq = stop > liq
    else:
        stop_before_liq = stop < liq
    out = {
        "side": side,
        "entry": entry,
        "stop": stop,
        "stop_distance_pct": round(abs(entry - stop) / entry * 100, 4),
        "risk_budget_usd": round(budget, 2),
        "qty": round(qty, 8),
        "notional_usd": round(notional, 2),
        "leverage": leverage,
        "margin_usd": round(margin, 2),
        "min_leverage_needed": round(notional / balance, 2) if balance else None,
        "fees_usd_round_trip_at_stop": round(qty * (entry + stop) * fee, 2),
        "loss_at_stop_usd": round(risk_total, 2),
        "loss_at_stop_pct_of_balance": round(risk_total / balance * 100, 3) if balance else None,
        "liquidation_price_est": round(liq, 8) if liq is not None else None,
        "stop_before_liquidation": stop_before_liq,
        "margin_fits_balance": margin <= balance,
        "targets": [],
    }
    for t in targets or []:
        gross = (t - entry) * qty if side == "long" else (entry - t) * qty
        net = gross - qty * (entry + t) * fee
        out["targets"].append({
            "price": t,
            "profit_usd": round(net, 2),
            "r_multiple": round(net / risk_total, 2) if risk_total else None,
        })
    return out


def render(r):
    lines = [
        "{side} | entry {entry} | stop {stop} ({d}% away)".format(
            side=r["side"].upper(), entry=r["entry"], stop=r["stop"], d=r["stop_distance_pct"]),
        "Risk budget:      ${:,.2f}".format(r["risk_budget_usd"]),
        "Quantity:         {}".format(r["qty"]),
        "Notional:         ${:,.2f}".format(r["notional_usd"]),
        "Leverage:         {}x  (margin ${:,.2f}; needs at least {}x)".format(
            r["leverage"], r["margin_usd"], r["min_leverage_needed"]),
        "Loss at stop:     ${:,.2f}  ({}% of balance, fees ${:,.2f} incl.)".format(
            r["loss_at_stop_usd"], r["loss_at_stop_pct_of_balance"], r["fees_usd_round_trip_at_stop"]),
    ]
    if r["liquidation_price_est"] is not None:
        lines.append("Liquidation est.: {}  -> stop {} liquidation".format(
            r["liquidation_price_est"], "is hit BEFORE" if r["stop_before_liquidation"] else "is hit AFTER (DANGER)"))
    if not r["margin_fits_balance"]:
        lines.append("WARNING: margin is larger than the balance. Raise leverage or cut size.")
    for t in r["targets"]:
        lines.append("Target {}: +${:,.2f}  ({}R)".format(t["price"], t["profit_usd"], t["r_multiple"]))
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=DEFAULT_CONFIG)
    p.add_argument("--balance", type=float, help="account balance in USDT (default: config account_size)")
    p.add_argument("--risk-pct", type=float, help="percent of balance to lose at the stop")
    p.add_argument("--risk-usd", type=float, help="fixed dollars to lose at the stop (overrides --risk-pct)")
    p.add_argument("--side", required=True, choices=["long", "short"])
    p.add_argument("--entry", type=float, required=True)
    p.add_argument("--stop", type=float, required=True)
    p.add_argument("--leverage", type=float)
    p.add_argument("--fee-pct", type=float, help="taker fee per side in percent (default 0.05)")
    p.add_argument("--mmr-pct", type=float, help="maintenance margin rate in percent (default 0.5)")
    p.add_argument("--qty-step", type=float, help="exchange lot step, rounds quantity down")
    p.add_argument("--targets", type=float, nargs="*", default=[])
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    cfg = load_json(a.config, {}) or {}
    balance = a.balance if a.balance is not None else cfg.get("account_size")
    if not balance:
        p.error("give --balance or set account_size in crypto/config.json")
    try:
        r = size_trade(
            balance=balance,
            risk_pct=a.risk_pct if a.risk_pct is not None else cfg.get("risk_per_trade_pct", 1),
            side=a.side, entry=a.entry, stop=a.stop,
            leverage=a.leverage if a.leverage is not None else cfg.get("default_leverage", 1),
            fee_pct=a.fee_pct if a.fee_pct is not None else cfg.get("taker_fee_pct", 0.05),
            mmr_pct=a.mmr_pct if a.mmr_pct is not None else cfg.get("maintenance_margin_pct", 0.5),
            targets=a.targets, risk_usd=a.risk_usd, qty_step=a.qty_step)
    except ValueError as e:
        print("Error: {}".format(e), file=sys.stderr)
        return 2
    print(json.dumps(r, indent=2) if a.json else render(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
