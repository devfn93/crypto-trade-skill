---
name: crypto-journal
description: >-
  Trade Journal for crypto. Logs every trade the user took (open, move
  stop, close with fees and funding) to crypto/journal.json, which the risk
  and prop tools read, and reviews performance: win rate, average win and
  loss, profit factor, expectancy, average R, worst losing streak, P&L by
  coin and by long/short. Use when the user says "log this trade", "I
  closed", "I got stopped out", "my stats", "review my trades", "what am I
  doing wrong", "import my history", "سجل الصفقة", "سكرت الصفقة", "احصائياتي".
---

# crypto-journal

The record of what really happened. Every other tool in this pack reads it,
so it must match the exchange.

`${CLAUDE_SKILL_DIR}` is this skill's folder.

```bash
python3 "${CLAUDE_SKILL_DIR}/journal.py" open --symbol ZECUSDT --side short --entry 520 --stop 545 --qty 0.97 --leverage 5
python3 "${CLAUDE_SKILL_DIR}/journal.py" move-stop --id 2 --stop 519
python3 "${CLAUDE_SKILL_DIR}/journal.py" close --id 2 --exit 470 --fees 0.48 --funding 0.05
python3 "${CLAUDE_SKILL_DIR}/journal.py" list --open
python3 "${CLAUDE_SKILL_DIR}/journal.py" stats
```

## Import from the exchange

```bash
python3 "${CLAUDE_SKILL_DIR}/import_csv.py" history.csv --tz-offset 3 --dry-run
python3 "${CLAUDE_SKILL_DIR}/import_csv.py" history.csv --tz-offset 3
python3 "${CLAUDE_SKILL_DIR}/import_csv.py" history.csv --map entry="Avg Entry" exit="Avg Exit"
```

Loads closed trades from a CSV export. Always run `--dry-run` first and check
the first lines with the user against the exchange: if longs and shorts look
swapped, the export lists the closing order, so add `--closing-side`. Use
`--map field=Column` for columns it did not find. Already-imported trades are
skipped. Never ask for API keys to fetch history: the user exports the file.

## Review: where the money is made and lost

```bash
python3 "${CLAUDE_SKILL_DIR}/review.py"            # local time from tz_offset_hours in the config
```

Breaks results down by coin, side, weekday, hour, holding time and tag
(`journal.py open ... --tags breakout retest`), and compares trades taken
after a loss with trades after a win, including quick re-entries (within 15
minutes of a loss). Read the findings with the user:

- Point at the biggest leak first (a coin, an hour, a side, revenge trades)
  and suggest one rule change at a time, e.g. a blocked symbol, a cooldown,
  no trades in a losing hour.
- Groups marked `(few)` are too small to conclude from. Under about 30 trades
  in total, everything is a hint, not a fact.
- A pattern in the past is not a promise. Suggest testing a change on demo.

## Steps

1. Log a trade only after the user says it filled, with the real fill
   price and quantity from the exchange. Times are UTC (`--opened`, `--closed`).
2. When a stop is moved, record it: open risk changes.
3. On close, use the real fees and funding if the user has them; otherwise
   the taker fee from the config is assumed on both sides.
4. For a review, run `stats` and read it with the user: is the edge real
   (expectancy above zero over enough trades), is one coin or one side
   losing, is the losing streak a risk for the drawdown limit. Point at
   patterns in the numbers; do not promise that a change will make money.
5. A trade copied from the exchange's history should be checked by the user;
   never invent missing prices.

## Fields

`id, symbol, side, entry, stop, qty, leverage, opened, status, exit, closed,
fees, funding, pnl_usd, initial_risk_usd, notes`

## Safety

- Education and arithmetic, not financial advice. Nothing here is a recommendation or promises returns. Crypto with leverage can lose the whole account fast.
- **Claude never places, edits, cancels or closes an order**, and never calls an exchange order tool. The user places every trade themselves.
- Claude never asks for, reads, stores or repeats API keys, secrets, passwords or seed phrases. If the user pastes one, tell them to delete the message and rotate the key.
- A stop loss on every trade unless the user has turned that rule off themselves. Never loosen a rule for the user.
- Paper or demo first. Going live is the user's own decision.
- Prices from free sources can be delayed; the exchange and the firm's dashboard are the final word.
