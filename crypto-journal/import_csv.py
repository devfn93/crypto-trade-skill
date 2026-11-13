#!/usr/bin/env python3
"""crypto-journal import: load closed trades from an exchange's CSV export.

  python3 import_csv.py history.csv --dry-run           # show what it understood
  python3 import_csv.py history.csv                     # add to crypto/journal.json
  python3 import_csv.py history.csv --map entry="Avg Entry" exit="Avg Exit" --tz-offset 3

Column names are detected from the header (symbol, side, entry price, exit
price, size, open / close time, fee, closed PnL, leverage, stop). Use --map
field=Column for anything it misses. Times without a zone are read as UTC
plus --tz-offset hours. Trades already in the journal are skipped.

Standard library only. It only reads the file you give it.
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys

JOURNAL = os.path.join("crypto", "journal.json")

ALIASES = {
    "symbol": ["symbol", "pair", "contract", "contracts", "instrument", "market", "ticker"],
    "side": ["side", "direction", "position side", "trade type", "type"],
    "entry": ["entry price", "avg entry price", "avg. entry price", "average entry price", "open price", "entry"],
    "exit": ["exit price", "avg exit price", "avg. exit price", "average exit price", "close price",
             "closing price", "exit"],
    "qty": ["qty", "quantity", "size", "closed size", "closed qty", "amount", "contracts qty", "volume"],
    "opened": ["open time", "opened", "entry time", "created time", "create time", "opening time", "created"],
    "closed": ["close time", "closed", "exit time", "closed time", "trade time", "updated time", "time", "date"],
    "fees": ["fee", "fees", "commission", "trading fee", "total fee"],
    "funding": ["funding", "funding fee"],
    "pnl": ["closed pnl", "realized pnl", "realised pnl", "closed p&l", "net pnl", "pnl", "profit", "p&l"],
    "leverage": ["leverage"],
    "stop": ["stop loss", "stop", "sl"],
}
REQUIRED = ["symbol", "side", "entry", "exit", "qty", "closed"]


def num(x):
    if x is None:
        return None
    s = str(x).replace(",", "").replace("$", "").replace("x", "").replace("X", "").strip()
    for unit in ("USDT", "USD", "USDC"):
        s = s.replace(unit, "").strip()
    if s in ("", "-", "--"):
        return None
    return float(s)


def parse_time(x, tz_offset=0.0):
    s = str(x).strip()
    try:
        v = float(s)
        if v > 1e11:
            v /= 1000.0
        return dt.datetime.fromtimestamp(v, dt.timezone.utc)
    except ValueError:
        pass
    s2 = s.replace("Z", "+00:00").replace("/", "-")
    for fmt in (None, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d-%m-%Y %H:%M:%S", "%m-%d-%Y %H:%M:%S", "%Y-%m-%d"):
        try:
            d = dt.datetime.fromisoformat(s2) if fmt is None else dt.datetime.strptime(s2, fmt)
        except ValueError:
            continue
        if d.tzinfo is None:
            d = d.replace(tzinfo=dt.timezone(dt.timedelta(hours=tz_offset)))
        return d.astimezone(dt.timezone.utc)
    raise ValueError("cannot read the time '{}'".format(s))


def iso(d):
    return d.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def side_of(x):
    s = str(x).lower()
    if any(k in s for k in ("short", "sell")):
        return "short"
    if any(k in s for k in ("long", "buy")):
        return "long"
    raise ValueError("cannot read the side '{}'".format(x))


def detect(header, overrides):
    low = {h.lower().strip(): h for h in header}
    mapping = {}
    for field, names in ALIASES.items():
        if field in overrides:
            if overrides[field] not in header:
                raise ValueError("--map {}: no column '{}'".format(field, overrides[field]))
            mapping[field] = overrides[field]
            continue
        for n in names:
            if n in low:
                mapping[field] = low[n]
                break
    return mapping


def read_trades(path, overrides=None, tz_offset=0.0, closing_side=False):
    with open(path, encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        mapping = detect(r.fieldnames or [], overrides or {})
        missing = [k for k in REQUIRED if k not in mapping]
        if missing:
            raise ValueError("could not find columns for: {}. Header is: {}. Use --map field=Column.".format(
                ", ".join(missing), ", ".join(r.fieldnames or [])))
        trades, errors = [], []
        for n, row in enumerate(r, 2):
            try:
                side = side_of(row[mapping["side"]])
                if closing_side:  # the export shows the closing order's side
                    side = "short" if side == "long" else "long"
                closed = parse_time(row[mapping["closed"]], tz_offset)
                opened = parse_time(row[mapping["opened"]], tz_offset) if mapping.get("opened") and row[mapping["opened"]] else closed
                t = {"symbol": row[mapping["symbol"]].upper().replace("-", "").replace("_", "").replace("/", "").strip(),
                     "side": side, "entry": num(row[mapping["entry"]]), "exit": num(row[mapping["exit"]]),
                     "qty": abs(num(row[mapping["qty"]])), "opened": iso(opened), "closed": iso(closed),
                     "status": "closed", "stop": None, "leverage": 1, "initial_risk_usd": None,
                     "notes": "imported"}
                for k in ("fees", "funding", "leverage", "stop"):
                    if mapping.get(k):
                        v = num(row[mapping[k]])
                        if v is not None:
                            t[k] = abs(v) if k == "fees" else v
                gross = (t["exit"] - t["entry"]) * t["qty"] * (1 if side == "long" else -1)
                if mapping.get("pnl") and num(row[mapping["pnl"]]) is not None:
                    t["pnl_usd"] = round(num(row[mapping["pnl"]]), 2)
                else:
                    t["pnl_usd"] = round(gross - (t.get("fees") or 0) - (t.get("funding") or 0), 2)
                if t.get("stop"):
                    t["initial_risk_usd"] = round(abs(t["entry"] - t["stop"]) * t["qty"], 2)
                trades.append(t)
            except (ValueError, TypeError, KeyError) as e:
                errors.append("line {}: {}".format(n, e))
    return trades, errors, mapping


def key(t):
    return (t["symbol"], t["side"], round(t["entry"], 8), round(t["qty"], 8), t["closed"])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("csv")
    p.add_argument("--journal", default=JOURNAL)
    p.add_argument("--map", nargs="*", default=[], metavar="field=Column")
    p.add_argument("--tz-offset", type=float, default=0.0, help="hours from UTC of the times in the file")
    p.add_argument("--closing-side", action="store_true",
                   help="the side column is the closing order (a Sell closes a long)")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    try:
        overrides = dict(m.split("=", 1) for m in a.map)
        trades, errors, mapping = read_trades(a.csv, overrides, a.tz_offset, a.closing_side)
    except (OSError, ValueError) as e:
        print("Error: {}".format(e), file=sys.stderr)
        return 2
    print("Columns used: " + ", ".join("{}={}".format(k, v) for k, v in mapping.items()))
    j = {"trades": []}
    if os.path.exists(a.journal):
        with open(a.journal, encoding="utf-8") as f:
            j = json.load(f)
    seen = {key(t) for t in j["trades"] if t.get("status") == "closed" and t.get("closed")}
    new = [t for t in trades if key(t) not in seen]
    nid = max([t["id"] for t in j["trades"]] or [0])
    for t in sorted(new, key=lambda t: t["closed"]):
        nid += 1
        t["id"] = nid
    print("{} trades read, {} new, {} already in the journal, {} lines skipped.".format(
        len(trades), len(new), len(trades) - len(new), len(errors)))
    for e in errors[:10]:
        print("  ! " + e)
    for t in sorted(new, key=lambda t: t["closed"])[:5]:
        print("  {closed}  {side:<5} {symbol:<10} qty {qty:<10g} {entry:g} -> {exit:g}  pnl ${pnl_usd:,.2f}".format(**t))
    if new:
        print("Net P&L of new trades: ${:,.2f}".format(sum(t["pnl_usd"] for t in new)))
        print("Check the first lines against the exchange. If long and short look swapped, use --closing-side.")
    if a.dry_run:
        print("Dry run: nothing written.")
        return 0
    j["trades"].extend(sorted(new, key=lambda t: t["closed"]))
    os.makedirs(os.path.dirname(a.journal) or ".", exist_ok=True)
    with open(a.journal, "w", encoding="utf-8") as f:
        json.dump(j, f, indent=2)
    print("Written to {}.".format(a.journal))
    return 0


if __name__ == "__main__":
    sys.exit(main())
