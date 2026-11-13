#!/usr/bin/env python3
"""crypto-journal: the trade log every other tool reads (crypto/journal.json).

  python3 journal.py open  --symbol BTCUSDT --side short --entry 97000 --stop 98200 --qty 0.02 --leverage 5
  python3 journal.py close --id 1 --exit 95500 [--fees 2.10]
  python3 journal.py move-stop --id 1 --stop 96900
  python3 journal.py list [--open]
  python3 journal.py stats [--symbol BTCUSDT] [--json]

Standard library only. It records what you tell it; it never trades.
"""
import argparse
import datetime as dt
import json
import os
import sys

JOURNAL = os.path.join("crypto", "journal.json")
CONFIG = os.path.join("crypto", "config.json")


def now_iso():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def trade_pnl(t, fee_pct):
    if t.get("exit") is None:
        return None
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


def stats(trades, fee_pct):
    closed = [t for t in trades if t.get("status") == "closed"]
    pnls = [trade_pnl(t, fee_pct) for t in closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    rs = []
    for t, p in zip(closed, pnls):
        r0 = t.get("initial_risk_usd")
        if r0:
            rs.append(p / r0)
    streak = worst = 0
    for p in pnls:
        streak = streak + 1 if p <= 0 else 0
        worst = max(worst, streak)
    gross_win, gross_loss = sum(wins), -sum(losses)
    by_symbol = {}
    for t, p in zip(closed, pnls):
        by_symbol[t["symbol"]] = round(by_symbol.get(t["symbol"], 0) + p, 2)
    by_side = {}
    for t, p in zip(closed, pnls):
        by_side[t["side"]] = round(by_side.get(t["side"], 0) + p, 2)
    n = len(pnls)
    return {
        "closed_trades": n,
        "open_trades": sum(1 for t in trades if t.get("status") == "open"),
        "net_pnl_usd": round(sum(pnls), 2),
        "win_rate_pct": round(len(wins) / n * 100, 1) if n else None,
        "avg_win_usd": round(gross_win / len(wins), 2) if wins else None,
        "avg_loss_usd": round(-gross_loss / len(losses), 2) if losses else None,
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else None,
        "expectancy_usd": round(sum(pnls) / n, 2) if n else None,
        "avg_r": round(sum(rs) / len(rs), 2) if rs else None,
        "max_consecutive_losses": worst,
        "pnl_by_symbol": by_symbol,
        "pnl_by_side": by_side,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--journal", default=JOURNAL)
    p.add_argument("--config", default=CONFIG)
    sub = p.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("open")
    o.add_argument("--symbol", required=True)
    o.add_argument("--side", required=True, choices=["long", "short"])
    o.add_argument("--entry", type=float, required=True)
    o.add_argument("--stop", type=float)
    o.add_argument("--qty", type=float, required=True)
    o.add_argument("--leverage", type=float, default=1)
    o.add_argument("--opened", help="ISO time, default now (UTC)")
    o.add_argument("--notes", default="")
    o.add_argument("--tags", nargs="*", default=[], help="setup names, e.g. breakout retest")
    c = sub.add_parser("close")
    c.add_argument("--id", type=int, required=True)
    c.add_argument("--exit", type=float, required=True)
    c.add_argument("--fees", type=float, help="actual fees paid; default = taker fee both sides")
    c.add_argument("--funding", type=float, help="funding paid (+) or received (-)")
    c.add_argument("--closed", help="ISO time, default now (UTC)")
    c.add_argument("--notes")
    m = sub.add_parser("move-stop")
    m.add_argument("--id", type=int, required=True)
    m.add_argument("--stop", type=float, required=True)
    ls = sub.add_parser("list")
    ls.add_argument("--open", action="store_true")
    st = sub.add_parser("stats")
    st.add_argument("--symbol")
    st.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    cfg = load(a.config, {})
    fee = cfg.get("taker_fee_pct", 0.05)
    j = load(a.journal, {"trades": []})
    trades = j["trades"]

    if a.cmd == "open":
        if a.stop is None and cfg.get("stop_loss_required", True):
            print("Refused: your rules require a stop loss on every trade (--stop).", file=sys.stderr)
            return 2
        t = {"id": max([x["id"] for x in trades] or [0]) + 1, "symbol": a.symbol.upper(),
             "side": a.side, "entry": a.entry, "stop": a.stop, "qty": a.qty,
             "leverage": a.leverage, "opened": a.opened or now_iso(), "status": "open",
             "notes": a.notes, "tags": [x.lower() for x in a.tags]}
        t["initial_risk_usd"] = round(risk_at_stop(t, fee), 2) if a.stop is not None else None
        trades.append(t)
        save(a.journal, j)
        print("Opened #{id} {side} {qty} {symbol} @ {entry}, stop {stop}, risk ${r}".format(r=t["initial_risk_usd"], **t))
        return 0

    def find(i):
        for t in trades:
            if t["id"] == i:
                return t
        raise SystemExit("No trade #{}".format(i))

    if a.cmd == "close":
        t = find(a.id)
        if t["status"] != "open":
            print("Trade #{} is already closed.".format(a.id), file=sys.stderr)
            return 2
        t.update({"exit": a.exit, "closed": a.closed or now_iso(), "status": "closed"})
        if a.fees is not None:
            t["fees"] = a.fees
        if a.funding is not None:
            t["funding"] = a.funding
        if a.notes:
            t["notes"] = (t.get("notes") + " | " if t.get("notes") else "") + a.notes
        t["pnl_usd"] = round(trade_pnl(t, fee), 2)
        save(a.journal, j)
        r0 = t.get("initial_risk_usd")
        print("Closed #{} at {}: {}${:,.2f}{}".format(
            a.id, a.exit, "+" if t["pnl_usd"] >= 0 else "-", abs(t["pnl_usd"]),
            " ({:.2f}R)".format(t["pnl_usd"] / r0) if r0 else ""))
        return 0

    if a.cmd == "move-stop":
        t = find(a.id)
        t["stop"] = a.stop
        save(a.journal, j)
        print("Trade #{} stop is now {}".format(a.id, a.stop))
        return 0

    if a.cmd == "list":
        for t in trades:
            if a.open and t["status"] != "open":
                continue
            pnl = t.get("pnl_usd")
            print("#{id:<3} {status:<6} {side:<5} {symbol:<10} qty {qty:<10} entry {entry:<10} stop {s:<10} {res}".format(
                s=t.get("stop"), res="" if pnl is None else "pnl ${:,.2f}".format(pnl), **t))
        return 0

    if a.cmd == "stats":
        ts = [t for t in trades if not a.symbol or t["symbol"] == a.symbol.upper()]
        s = stats(ts, fee)
        if a.json:
            print(json.dumps(s, indent=2))
        else:
            for k, v in s.items():
                print("{:<24} {}".format(k, v))
        return 0


if __name__ == "__main__":
    sys.exit(main())
