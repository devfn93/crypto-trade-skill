---
name: crypto-risk
description: >-
  Risk Manager for crypto trades. Checks every planned trade against the
  user's rules before they place it and blocks anything over them: stop loss
  required, max risk per trade, max leverage, liquidation before the stop,
  minimum reward:risk, margin vs balance, max open positions and total open
  risk, daily loss room and max drawdown room (prop-firm style), blocked or
  allowed symbols, shorts, duplicates and trades per day. Prints PASS or
  BLOCK with the reason, and a ticket for each PASS. Use when the user says
  "check my trade", "is this safe", "risk check", "does this break my
  rules", "can I take this", "فحص المخاطر", "هل الصفقة آمنة", or before
  any trade, always.
argument-hint: "[path to plan.json]"
---

# crypto-risk

The gate between an idea and the exchange. A BLOCK is final for that trade.
A PASS only means the trade fits the rules: it is not a recommendation, and
the user still decides and places it themselves.

`${CLAUDE_SKILL_DIR}` is this skill's folder.

```bash
python3 "${CLAUDE_SKILL_DIR}/check.py"              # crypto/plan.json; writes crypto/state/risk.json
python3 "${CLAUDE_SKILL_DIR}/check.py" --json
python3 "${CLAUDE_SKILL_DIR}/check.py" --no-write
```

## Files

| file | what |
| --- | --- |
| `crypto/plan.json` | planned trades: `{"orders": [{"symbol","side","entry","stop","targets","leverage","qty"?}]}` |
| `crypto/config.json` | the rules (from `config.example.json`) |
| `crypto/journal.json` | open trades and today's closed trades (from `/crypto-journal`) |
| `crypto/state/risk.json` | the verdicts, each with a fingerprint of the exact trade |

If a trade has no `qty`, it is sized from `risk_per_trade_pct`, capped by the
daily and drawdown room left.

## The checks

Trades are checked in order, as if each passed trade were already open, so a
batch that is fine one by one but too much together is caught.

| check | blocks when |
| --- | --- |
| format | no symbol, side not long/short, bad prices, stop on the wrong side |
| stop | no stop while `stop_loss_required` is true |
| asset | on `blocked_symbols`, not on `allowed_symbols` (if set), short while `allow_short` is false |
| leverage | over `max_leverage`, or liquidation comes before the stop |
| risk | loss at stop over `max_risk_per_trade_pct` of balance; size over `max_notional_usd` (0 = no cap) |
| reward | first target under `min_rr`, or on the wrong side |
| margin | this margin plus open margin is more than the balance |
| exposure | over `max_open_positions` or `max_total_open_risk_pct` |
| daily loss | the loss at stop is more than the daily loss room left |
| drawdown | the loss at stop could break the max drawdown floor |
| frequency | over `max_trades_per_day`; same symbol and side already open or planned |

Warnings do not block, but say them: an open trade without a stop, a LIVE
account, no target given.

## Steps

1. Make sure `crypto/journal.json` is up to date (open trades, today's closes).
   If the user trades on a prop firm, run `/crypto-prop` first.
2. Write the trades to `crypto/plan.json` and run `check.py`.
3. Tell the user the result trade by trade in plain words. For a BLOCK give
   the reason and the fix (smaller size, closer stop, lower leverage, wait
   for the daily reset). Never change a rule yourself.
4. Show the ticket for each PASS. The user places it on their exchange, with
   the stop in the same order. Claude does not place it.
5. If a trade changes in any way, check it again.
6. After the user says it filled, log it with `/crypto-journal open`.

## Example

$2,500 demo account, rules from the example config, one losing BTC short
already today (-$25.95):

```
PASS  #1 short ZECUSDT  risk $24.74
BLOCK  #2 short QNTUSDT  risk $24.74
      - leverage 20.0x is over your max 10x
      - reward:risk 1.43 is under your minimum 1.5
BLOCK  #3 long ETHUSDT
      - no stop loss (your rules require one on every trade)
```

## Safety

- Education and arithmetic, not financial advice. Nothing here is a recommendation or promises returns. Crypto with leverage can lose the whole account fast.
- **Claude never places, edits, cancels or closes an order**, and never calls an exchange order tool. The user places every trade themselves.
- Claude never asks for, reads, stores or repeats API keys, secrets, passwords or seed phrases. If the user pastes one, tell them to delete the message and rotate the key.
- A stop loss on every trade unless the user has turned that rule off themselves. Never loosen a rule for the user.
- Paper or demo first. Going live is the user's own decision.
- Prices from free sources can be delayed; the exchange and the firm's dashboard are the final word.
