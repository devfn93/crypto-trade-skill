---
name: crypto-backtest
description: >-
  Strategy Backtester for crypto. Tests a simple entry rule (breakout, EMA
  cross, RSI) with an ATR stop and an R-multiple target on past candles,
  fees included, and reports the number of trades, win rate, expectancy in R,
  profit factor, max drawdown, longest losing streak and whether the first
  and second half of the data agree. Use before trading a rule with real
  money, or when the user says "backtest", "does this strategy work", "test
  my strategy", "what win rate", "جرب الاستراتيجية", "اختبر الطريقة",
  "هل تربح".
argument-hint: "[candles file] [strategy]"
---

# crypto-backtest

Answers one question honestly: on past data, after fees, did this rule make
or lose money, and how rough was the ride? It is the step before risking
money on a rule, and the numbers it gives feed `/crypto-prop` (simulate).

`${CLAUDE_SKILL_DIR}` is this skill's folder.

```bash
python3 "${CLAUDE_SKILL_DIR}/backtest.py" candles.csv --strategy breakout --lookback 20 --rr 2
python3 "${CLAUDE_SKILL_DIR}/backtest.py" candles.json --strategy ema-cross --fast 20 --slow 50 --side short
python3 "${CLAUDE_SKILL_DIR}/backtest.py" candles.csv --strategy rsi --atr-mult 1.5 --rr 1.5 --list
```

## Step 1: get candles

- From a connected market-data connector: fetch as many candles as it gives
  for the coin and timeframe and save them as JSON (`t, o, h, l, c, v`).
- Or a CSV the user exports from their exchange or charting site (`time,
  open, high, low, close`).
- More history is better: aim for 100+ trades. Under 30 trades proves nothing.

## Step 2: run it

| flag | meaning |
| --- | --- |
| `--strategy` | `breakout` (N-candle high/low), `ema-cross` (fast/slow), `rsi` (30/70 re-cross) |
| `--side` | `long`, `short` or `both` |
| `--atr-mult` | stop distance in ATR(14) |
| `--rr` | target as a multiple of the stop distance |
| `--max-bars` | close after N candles if neither is hit |
| `--fee-pct` | taker fee per side |

Entry is at the next candle's open. If one candle touches both the stop and
the target, the stop is counted.

## Step 3: read the result with the user

- **expectancy_r** above zero after fees is the minimum. Below zero: do not
  trade this rule; no position sizing fixes it.
- **max_drawdown_r** and **max_consecutive_losses** at the user's risk per
  trade: would that streak break the challenge's drawdown? (12 losses in a
  row at 1% is 12%.)
- **first half vs second half**: if they disagree, the edge is not stable.
- Then pass the win rate and average win/loss in R to
  `/crypto-prop` → `simulate.py` to choose the risk per trade.

## Honesty rules

- Never tune settings until the result looks good and present that as an
  edge: that is curve fitting. If several settings were tried, say how many.
- Say what the test leaves out: slippage, funding, gaps, the user's own
  execution. Real results are usually worse.
- A good backtest is a reason to try the rule small on a demo account, not a
  reason to expect profit.

## Safety

- Education and arithmetic, not financial advice. Nothing here is a recommendation or promises returns. Crypto with leverage can lose the whole account fast.
- **Claude never places, edits, cancels or closes an order**, and never calls an exchange order tool. The user places every trade themselves.
- Claude never asks for, reads, stores or repeats API keys, secrets, passwords or seed phrases. If the user pastes one, tell them to delete the message and rotate the key.
- A stop loss on every trade unless the user has turned that rule off themselves. Never loosen a rule for the user.
- Paper or demo first. Going live is the user's own decision.
- Prices from free sources can be delayed; the exchange and the firm's dashboard are the final word.
