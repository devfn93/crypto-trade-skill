---
name: crypto-size
description: >-
  Position Sizer for crypto futures and spot. Turns "I'll risk 1%" into an
  exact quantity from the entry and the stop, fees included, and shows the
  notional, margin, the leverage really needed, the liquidation price
  estimate (isolated, USDT-margined) and whether the stop is hit before
  liquidation, plus profit and R multiple at each target. Use when the user
  says "how much should I buy", "position size", "what size for this trade",
  "how many contracts", "what leverage", "where is my liquidation", "حجم
  الصفقة", "كم ادخل", "كم الرافعة".
argument-hint: "[side entry stop]"
---

# crypto-size

Sizes one trade from the money the user agreed to lose at the stop. Size
comes from risk, not from leverage: leverage only decides the margin.

`${CLAUDE_SKILL_DIR}` is this skill's folder.

```bash
python3 "${CLAUDE_SKILL_DIR}/size.py" --side short --entry 97000 --stop 98200 --targets 95000 93000
python3 "${CLAUDE_SKILL_DIR}/size.py" --balance 2500 --risk-pct 0.5 --side long --entry 3.12 --stop 2.98 --leverage 3
python3 "${CLAUDE_SKILL_DIR}/size.py" --risk-usd 20 --side long --entry 0.452 --stop 0.438 --qty-step 1 --json
```

It reads `crypto/config.json` for the balance, risk percent, leverage, taker
fee and maintenance margin when flags are not given (start from
`config.example.json` at the root of this pack).

## Steps

1. Get side, entry and stop from the user. No stop, no size: ask where the
   trade is wrong. Never invent a stop.
2. Run `size.py`. Use the exchange's lot step (`--qty-step`) if the user knows it.
3. Show in plain words: quantity, notional, margin, loss at the stop in
   dollars and percent, liquidation estimate, and the R at each target.
4. If the stop comes AFTER liquidation, say so first: lower the leverage.
   If the margin is more than the balance, the trade is too big.
5. Hand it to `/crypto-risk` before the user places anything.

## The maths

- risk per unit = |entry - stop| + (entry + stop) x taker fee
- quantity = risk budget / risk per unit
- margin = quantity x entry / leverage
- liquidation (isolated, linear): long = entry x (1 - 1/leverage + mmr),
  short = entry x (1 + 1/leverage - mmr). Exchanges add tiers and fees, so
  the real level is a little closer: keep a margin of safety.

## Example

$2,500 account, 1% risk, short BTC at 97,000, stop 98,200, 5x:
quantity 0.01927 BTC (~$1,869), margin $374, loss at stop $25.00 with fees,
liquidation ~115,915 (stop is hit first), target 95,000 = +$36.68 (1.47R).

## Safety

- Education and arithmetic, not financial advice. Nothing here is a recommendation or promises returns. Crypto with leverage can lose the whole account fast.
- **Claude never places, edits, cancels or closes an order**, and never calls an exchange order tool. The user places every trade themselves.
- Claude never asks for, reads, stores or repeats API keys, secrets, passwords or seed phrases. If the user pastes one, tell them to delete the message and rotate the key.
- A stop loss on every trade unless the user has turned that rule off themselves. Never loosen a rule for the user.
- Paper or demo first. Going live is the user's own decision.
- Prices from free sources can be delayed; the exchange and the firm's dashboard are the final word.
