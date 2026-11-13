---
name: crypto-prop
description: >-
  Prop Firm Guard for crypto funded-account challenges. Tracks the account
  against the firm's rules from the trade journal: balance, today's P&L,
  daily loss used and left, max drawdown used and left (static or
  trailing), profit target progress, trading days, and the most the next
  trade may risk without breaking a rule. Says STOP when a limit is used
  up. Also simulates thousands of challenges to compare pass and bust rates
  at each risk size. Use when the user says "how much can I lose today", "am I safe",
  "challenge status", "drawdown left", "daily loss", "prop firm rules",
  "funded account", "what risk should I use", "chance to pass", "حالة التحدي", "كم باقي خسارة يومية", "الدرو داون".
---

# crypto-prop

Most challenges are lost by breaking one rule on one bad day, not by bad
analysis. This skill keeps the rules in front of the user before every trade.

`${CLAUDE_SKILL_DIR}` is this skill's folder.

```bash
python3 "${CLAUDE_SKILL_DIR}/prop.py"           # exit 0 = room left, 1 = a limit is used up
python3 "${CLAUDE_SKILL_DIR}/prop.py" --json
```

## Step 1: write the firm's rules once

Copy `config.example.json` (pack root) to `crypto/config.json` and fill it
from the firm's own rules page, in the user's words. Ask, do not assume:

| key | ask |
| --- | --- |
| `account_size` | the challenge account size |
| `daily_loss_limit_pct` | the daily loss limit |
| `daily_loss_base` | is it measured from the day's starting balance (`start_of_day`) or the initial balance (`initial`)? |
| `day_reset_utc` | when the firm's day resets, in UTC (Baghdad is UTC+3) |
| `max_drawdown_pct`, `drawdown_type` | max loss, and is it `static` (from the start) or `trailing` (from the high point)? |
| `trailing_locks_at_initial` | does a trailing floor stop rising once it reaches the start balance? |
| `profit_target_pct`, `min_trading_days` | to pass the phase |
| `max_leverage`, `stop_loss_required`, `max_risk_per_trade_pct` | per-trade rules |

If a rule is unclear, say so and point the user to the firm's rules page or
support. Never guess a limit in the user's favour: when in doubt, pick the
stricter reading and say which one you picked.

## Step 2: check before every trading session and every trade

1. Bring `crypto/journal.json` up to date (`/crypto-journal`).
2. Run `prop.py` and tell the user in plain words: how much they may still
   lose today, how far the drawdown floor is, and the most the next trade
   may risk.
3. If it says STOP, say it plainly: no new trades until the reset (daily) or
   at all (drawdown). Do not help size a trade that would break a rule.
4. Open trades without a stop are unknown risk: flag them first.

## Step 3: choose the risk per trade with numbers

```bash
python3 "${CLAUDE_SKILL_DIR}/simulate.py" --win-rate 45 --avg-win-r 2 --avg-loss-r 1
python3 "${CLAUDE_SKILL_DIR}/simulate.py" --from-journal      # the user's real results, 20+ trades
```

It runs thousands of random challenges under the firm's rules and prints, for
each risk size, how often the challenge passes, breaks a rule, or runs out of
time. `raw` takes every trade at full size; `guarded` never risks more than
the room left (what `/crypto-risk` enforces).

- Read it as a comparison between risk sizes: where does the pass rate stop
  rising while the bust rate keeps climbing? That is usually the size to stay under.
- If expectancy is zero or negative, say so plainly: no risk size helps;
  the strategy needs work first (`/crypto-backtest`, `/crypto-journal` review).
- It assumes independent trades and that past numbers hold. Never present a
  pass percentage as a forecast.

## Notes

- The tool counts closed trades plus the worst case of open trades (loss to
  their stops). Firms that count floating equity can be stricter during a
  trade: compare with the firm's dashboard, which is the final word.
- Fees and funding reduce the balance too; log them when closing.

## Example

```
Balance          $2,474.05  (start $2,500.00, -1.04%)
Today            -$25.95 realized, 0 open trade(s) risking $0.00
Daily loss       limit $125.00  ->  room left $99.05
Max drawdown     floor $2,250.00 (static)  ->  room left $224.05
Profit target    10%  ->  $275.95 to go
Next trade may risk at most $99.05 without breaking a rule
```

## Safety

- Education and arithmetic, not financial advice. Nothing here is a recommendation or promises returns. Crypto with leverage can lose the whole account fast.
- **Claude never places, edits, cancels or closes an order**, and never calls an exchange order tool. The user places every trade themselves.
- Claude never asks for, reads, stores or repeats API keys, secrets, passwords or seed phrases. If the user pastes one, tell them to delete the message and rotate the key.
- A stop loss on every trade unless the user has turned that rule off themselves. Never loosen a rule for the user.
- Paper or demo first. Going live is the user's own decision.
- Prices from free sources can be delayed; the exchange and the firm's dashboard are the final word.
