---
name: crypto-journal
description: >-
  Trade Journal for crypto. Logs every trade the user took (open, move
  stop, close with fees and funding) to crypto/journal.json, which the risk
  and prop tools read, and reviews performance: win rate, average win and
  loss, profit factor, expectancy, average R, worst losing streak, P&L by
  coin and by long/short. Use when the user says "log this trade", "I
  closed", "I got stopped out", "my stats", "review my trades", "what am I
  doing wrong", "سجل الصفقة", "سكرت الصفقة", "احصائياتي".
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
