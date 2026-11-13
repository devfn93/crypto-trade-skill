#!/usr/bin/env python3
"""crypto-backtest: test a simple trading rule on past candles before risking money.

Candles: a CSV with a header (time, open, high, low, close[, volume]) or a JSON
list of objects ({"t","o","h","l","c","v"} or full names) or of arrays
[time, open, high, low, close, volume]. Oldest first, or it is sorted for you.

  python3 backtest.py candles.csv --strategy breakout --lookback 20 --rr 2
  python3 backtest.py candles.json --strategy ema-cross --fast 20 --slow 50 --side both
  python3 backtest.py candles.csv --strategy rsi --rr 1.5 --atr-mult 1.5 --json

Rules (entry at the next candle's open, one position at a time):
  breakout    close above the highest high / below the lowest low of the last N candles
  ema-cross   fast EMA crosses the slow EMA
  rsi         RSI(14) comes back up through 30 (long) / down through 70 (short)

Stop = ATR(14) x --atr-mult from the entry. Target = --rr x the stop distance.
If one candle touches both the stop and the target, the stop is counted
(the cautious reading). Fees are charged on both sides.

A backtest shows how a rule behaved in the past. It is not a promise.
Standard library only.
"""
import argparse
import csv
import json
import sys


def _num(x):
    return float(str(x).replace(",", ""))


def load_candles(path):
    with open(path, encoding="utf-8-sig") as f:
        text = f.read()
    rows = []
    if text.lstrip()[:1] in "[{":
        data = json.loads(text)
        if isinstance(data, dict):
            for k in ("data", "result", "candles"):
                if k in data:
                    data = data[k]
                    break
            if isinstance(data, dict):
                data = data.get("data", [])
        for d in data:
            if isinstance(d, dict):
                g = lambda *ks: next(d[k] for k in ks if k in d)
                rows.append((g("t", "time", "timestamp", "date"), _num(g("o", "open")), _num(g("h", "high")),
                             _num(g("l", "low")), _num(g("c", "close"))))
            else:
                rows.append((d[0], _num(d[1]), _num(d[2]), _num(d[3]), _num(d[4])))
    else:
        r = csv.DictReader(text.splitlines())
        names = {n.lower().strip(): n for n in r.fieldnames or []}

        def col(*opts):
            for o in opts:
                if o in names:
                    return names[o]
            raise ValueError("no column named any of: " + ", ".join(opts))
        ct, co, ch, cl, cc = (col("time", "timestamp", "date", "datetime", "open time", "t"), col("open", "o"),
                              col("high", "h"), col("low", "l"), col("close", "c"))
        for d in r:
            rows.append((d[ct], _num(d[co]), _num(d[ch]), _num(d[cl]), _num(d[cc])))
    try:
        rows.sort(key=lambda x: float(x[0]))
    except (TypeError, ValueError):
        rows.sort(key=lambda x: str(x[0]))
    return [{"t": r[0], "o": r[1], "h": r[2], "l": r[3], "c": r[4]} for r in rows]


def ema(values, n):
    out, k, e = [], 2.0 / (n + 1), None
    for i, v in enumerate(values):
        e = v if e is None else v * k + e * (1 - k)
        out.append(e if i >= n - 1 else None)
    return out


def atr(c, n=14):
    out, prev, a = [], None, None
    trs = []
    for i, x in enumerate(c):
        tr = x["h"] - x["l"] if prev is None else max(x["h"] - x["l"], abs(x["h"] - prev), abs(x["l"] - prev))
        prev = x["c"]
        trs.append(tr)
        if i + 1 < n:
            out.append(None)
        elif i + 1 == n:
            a = sum(trs) / n
            out.append(a)
        else:
            a = (a * (n - 1) + tr) / n
            out.append(a)
    return out


def rsi(closes, n=14):
    out, ag, al = [None], None, None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        g, l = max(d, 0.0), max(-d, 0.0)
        if ag is None:
            gains.append(g)
            losses.append(l)
            if len(gains) == n:
                ag, al = sum(gains) / n, sum(losses) / n
        else:
            ag, al = (ag * (n - 1) + g) / n, (al * (n - 1) + l) / n
        out.append(None if ag is None else (100.0 if al == 0 else 100 - 100 / (1 + ag / al)))
    return out


def signals(c, strategy, lookback=20, fast=20, slow=50):
    """+1 long, -1 short, 0 nothing, decided on each candle's close."""
    n = len(c)
    sig = [0] * n
    closes = [x["c"] for x in c]
    if strategy == "breakout":
        for i in range(lookback, n):
            hh = max(x["h"] for x in c[i - lookback:i])
            ll = min(x["l"] for x in c[i - lookback:i])
            if closes[i] > hh:
                sig[i] = 1
            elif closes[i] < ll:
                sig[i] = -1
    elif strategy == "ema-cross":
        f, s = ema(closes, fast), ema(closes, slow)
        for i in range(1, n):
            if None in (f[i], s[i], f[i - 1], s[i - 1]):
                continue
            if f[i - 1] <= s[i - 1] and f[i] > s[i]:
                sig[i] = 1
            elif f[i - 1] >= s[i - 1] and f[i] < s[i]:
                sig[i] = -1
    elif strategy == "rsi":
        r = rsi(closes)
        for i in range(1, n):
            if r[i] is None or r[i - 1] is None:
                continue
            if r[i - 1] < 30 <= r[i]:
                sig[i] = 1
            elif r[i - 1] > 70 >= r[i]:
                sig[i] = -1
    else:
        raise ValueError("unknown strategy " + strategy)
    return sig


def run(c, strategy="breakout", side="both", rr=2.0, atr_mult=1.5, fee_pct=0.05, max_bars=0, **kw):
    sig = signals(c, strategy, **kw)
    a = atr(c)
    fee = fee_pct / 100.0
    trades, i, n = [], 0, len(c)
    while i < n - 1:
        s = sig[i]
        if s == 0 or a[i] is None or (s == 1 and side == "short") or (s == -1 and side == "long"):
            i += 1
            continue
        entry = c[i + 1]["o"]
        dist = a[i] * atr_mult
        if dist <= 0:
            i += 1
            continue
        stop = entry - s * dist
        target = entry + s * dist * rr
        exit_price, why, j = None, None, i + 1
        while j < n:
            x = c[j]
            hit_stop = x["l"] <= stop if s == 1 else x["h"] >= stop
            hit_tgt = x["h"] >= target if s == 1 else x["l"] <= target
            if hit_stop:
                exit_price, why = stop, "stop"
                break
            if hit_tgt:
                exit_price, why = target, "target"
                break
            if max_bars and j - i >= max_bars:
                exit_price, why = x["c"], "time"
                break
            j += 1
        if exit_price is None:
            break  # still open at the end of the data: not counted
        risk = dist + (entry + stop) * fee
        pnl = s * (exit_price - entry) - (entry + exit_price) * fee
        trades.append({"entry_time": c[i + 1]["t"], "exit_time": c[j]["t"], "side": "long" if s == 1 else "short",
                       "entry": entry, "stop": round(stop, 8), "exit": round(exit_price, 8), "why": why,
                       "bars": j - i, "r": round(pnl / risk, 3)})
        i = j + 1
    return trades


def summarize(trades, risk_pct=1.0):
    rs = [t["r"] for t in trades]
    n = len(rs)
    if not n:
        return {"trades": 0}
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    eq = peak = dd = 0.0
    streak = worst = 0
    bal = 100.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
        streak = streak + 1 if r <= 0 else 0
        worst = max(worst, streak)
        bal *= 1 + r * risk_pct / 100.0
    half = n // 2
    exp1 = sum(rs[:half]) / half if half else None
    exp2 = sum(rs[half:]) / (n - half)
    out = {
        "trades": n,
        "win_rate_pct": round(len(wins) / n * 100, 1),
        "avg_win_r": round(sum(wins) / len(wins), 2) if wins else None,
        "avg_loss_r": round(sum(losses) / len(losses), 2) if losses else None,
        "expectancy_r": round(sum(rs) / n, 3),
        "total_r": round(sum(rs), 2),
        "profit_factor": round(sum(wins) / -sum(losses), 2) if losses and sum(losses) < 0 else None,
        "max_drawdown_r": round(dd, 2),
        "max_consecutive_losses": worst,
        "return_pct_at_{}pct_risk".format(risk_pct): round(bal - 100, 2),
        "expectancy_first_half_r": round(exp1, 3) if exp1 is not None else None,
        "expectancy_second_half_r": round(exp2, 3),
        "warnings": [],
    }
    w = out["warnings"]
    if n < 30:
        w.append("only {} trades: too few to trust. Use more history.".format(n))
    if exp1 is not None and (exp1 > 0) != (exp2 > 0):
        w.append("the first and second half disagree: the edge is not stable.")
    if out["expectancy_r"] <= 0:
        w.append("expectancy is not above zero after fees: this rule lost money on this data.")
    w.append("past results do not predict future results; settings tuned to fit the past usually fail live.")
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("candles")
    p.add_argument("--strategy", default="breakout", choices=["breakout", "ema-cross", "rsi"])
    p.add_argument("--side", default="both", choices=["long", "short", "both"])
    p.add_argument("--lookback", type=int, default=20)
    p.add_argument("--fast", type=int, default=20)
    p.add_argument("--slow", type=int, default=50)
    p.add_argument("--rr", type=float, default=2.0, help="target as a multiple of the stop distance")
    p.add_argument("--atr-mult", type=float, default=1.5, help="stop distance in ATR(14)")
    p.add_argument("--fee-pct", type=float, default=0.05)
    p.add_argument("--max-bars", type=int, default=0, help="close after this many candles (0 = off)")
    p.add_argument("--risk-pct", type=float, default=1.0)
    p.add_argument("--list", action="store_true", help="print every trade")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    try:
        c = load_candles(a.candles)
    except (OSError, ValueError, KeyError, StopIteration, IndexError) as e:
        print("Could not read candles: {}".format(e), file=sys.stderr)
        return 2
    if len(c) < 60:
        print("Only {} candles: need at least 60.".format(len(c)), file=sys.stderr)
        return 2
    trades = run(c, a.strategy, a.side, a.rr, a.atr_mult, a.fee_pct, a.max_bars,
                 lookback=a.lookback, fast=a.fast, slow=a.slow)
    s = summarize(trades, a.risk_pct)
    if a.json:
        print(json.dumps({"summary": s, "trades": trades if a.list else None}, indent=2))
        return 0
    print("{} on {} candles ({} -> {})  side {}  stop {} ATR  target {}R  fee {}%".format(
        a.strategy, len(c), c[0]["t"], c[-1]["t"], a.side, a.atr_mult, a.rr, a.fee_pct))
    if a.list:
        for t in trades:
            print("  {entry_time}  {side:<5} entry {entry:<12g} exit {exit:<12g} {why:<6} {r:+.2f}R".format(**t))
    for k, v in s.items():
        if k != "warnings":
            print("{:<32} {}".format(k, v))
    for w in s.get("warnings", []):
        print("! " + w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
