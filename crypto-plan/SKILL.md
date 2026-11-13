---
name: crypto-plan
description: >-
  Trade Planner for crypto. Turns a trade idea into a written plan before any
  money moves: market context from live data (price, 24h range, candles on a
  few timeframes, trend structure, support and resistance, ATR, volume,
  funding rate where available, news that touches the coin), a clear reason
  to enter, where the idea is wrong (the stop), targets, and what would
  cancel it. Writes crypto/plan.json for the sizer and the risk check. Use
  when the user says "analyse BTC", "should I short this", "plan a trade",
  "where is support", "what do you think of this chart", "حلل", "خطة صفقة",
  "وين الدعم", or shares a chart screenshot.
argument-hint: "[symbol] [timeframe]"
---

# crypto-plan

A plan is written before the trade, not after. It does not predict the
price: it says what has to be true for the idea, where it is wrong, and how
much that costs. The user decides.

The full flow of the pack:

```
crypto-prop (room left today) -> crypto-plan -> crypto-size -> crypto-risk -> user places it -> crypto-journal
```

## Step 1: get real data

Use what this session has, in this order, and say where each number came from
and its time (UTC and the user's local time):

1. A connected market-data connector (for example an exchange's public
   market-data tools: ticker, candlesticks, order book, mark price).
2. A chart screenshot the user shares: read the levels from it and say they
   are read from the image.
3. Public price pages via web search.

Never invent a price, a level or a funding rate. If data is missing, say so.

## Step 2: read the market

For the coin, on the user's timeframe and one higher one:

- **Trend structure**: higher highs and higher lows (up), lower highs and lower
  lows (down), or a range. Where the last swing high and low are.
- **Levels**: nearest support and resistance from swing points and the 24h /
  weekly range; round numbers.
- **Volatility**: ATR(14) on the trading timeframe. A stop tighter than about
  1 ATR is usually noise.
- **Volume**: is the move on rising or falling volume.
- **Derivatives** (if available): funding rate and open interest. Very high
  positive funding means crowded longs; very negative, crowded shorts.
- **Correlation**: what BTC is doing; most coins follow it.
- **News and events**: listings, unlocks, hacks, macro data (CPI, FOMC) in the
  next hours. Say if a big event is close.

Keep it short: a few lines, with numbers.

## Step 3: write the plan

| item | what |
| --- | --- |
| idea | long or short, and the reason in one sentence |
| entry | price or zone, limit or market |
| stop | where the idea is wrong (beyond a level, about 1 ATR or more) |
| targets | 1 to 3, at the next levels; give R for each |
| cancel if | what would kill the idea before entry (e.g. a close above X) |
| time | how long the idea is valid |

Write it to `crypto/plan.json`:

```json
{"orders": [{"symbol": "ZECUSDT", "side": "short", "entry": 520, "stop": 545,
             "targets": [470, 440], "leverage": 5, "type": "limit"}]}
```

Then size it with `/crypto-size` and check it with `/crypto-risk`. A plan that
fails the risk check is not taken as it is.

## How to talk about it

- Give both sides: what supports the idea and what argues against it.
- Never say a trade "will" work, never give a win probability you cannot back.
- If the user is about to trade against their own rules (no stop, revenge
  trade after a loss, over the daily limit), say it plainly and kindly.
- If the user asks Claude to decide for them, set out the plan and the
  numbers and leave the choice with them.

## Safety

- Education and arithmetic, not financial advice. Nothing here is a recommendation or promises returns. Crypto with leverage can lose the whole account fast.
- **Claude never places, edits, cancels or closes an order**, and never calls an exchange order tool. The user places every trade themselves.
- Claude never asks for, reads, stores or repeats API keys, secrets, passwords or seed phrases. If the user pastes one, tell them to delete the message and rotate the key.
- A stop loss on every trade unless the user has turned that rule off themselves. Never loosen a rule for the user.
- Paper or demo first. Going live is the user's own decision.
- Prices from free sources can be delayed; the exchange and the firm's dashboard are the final word.
