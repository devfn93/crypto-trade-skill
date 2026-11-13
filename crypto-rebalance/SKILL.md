---
name: crypto-rebalance
description: >-
  Spot Portfolio Rebalancer for crypto. Values the user's spot holdings at
  current prices, shows each coin's drift from its target weight (with
  USDT as the cash slice), and proposes only the trades for coins outside
  the band, sells before buys, skipping tiny trades and checking there is
  enough USDT after fees. Use when the user says "rebalance my portfolio",
  "my coins drifted", "back to my weights", "DCA plan", "توزيع المحفظة",
  "اعادة توازن".
---

# crypto-rebalance

For a long-term spot portfolio, not for futures.

`${CLAUDE_SKILL_DIR}` is this skill's folder.

```bash
python3 "${CLAUDE_SKILL_DIR}/rebalance.py" --band 5 --min-trade 20
python3 "${CLAUDE_SKILL_DIR}/rebalance.py" --json
```

## Files

| file | example |
| --- | --- |
| `crypto/spot.json` | `{"holdings": {"BTC": 0.01, "ETH": 0.5}, "cash_usdt": 300}` |
| `crypto/prices.json` | `{"BTC": 97000, "ETH": 3400}` |
| `crypto/targets.json` | `{"BTC": 50, "ETH": 30, "USDT": 20}` (percent) |

## Steps

1. Get the holdings from the user (or a balances export they paste). Never
   ask for exchange keys to read them.
2. Get current prices from a market-data connector if one is connected, or
   from a public price page, and write `crypto/prices.json` with the time.
3. Run `rebalance.py`, show the drift table and the trades.
4. The user places the trades themselves, sells first.

## Safety

- Education and arithmetic, not financial advice. Nothing here is a recommendation or promises returns. Crypto with leverage can lose the whole account fast.
- **Claude never places, edits, cancels or closes an order**, and never calls an exchange order tool. The user places every trade themselves.
- Claude never asks for, reads, stores or repeats API keys, secrets, passwords or seed phrases. If the user pastes one, tell them to delete the message and rotate the key.
- A stop loss on every trade unless the user has turned that rule off themselves. Never loosen a rule for the user.
- Paper or demo first. Going live is the user's own decision.
- Prices from free sources can be delayed; the exchange and the firm's dashboard are the final word.
