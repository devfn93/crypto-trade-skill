# Configuration · الإعدادات

All rules live in one file: `crypto/config.json`. Copy the example and edit it:

```bash
mkdir -p crypto
cp config.example.json crypto/config.json
```

كل القواعد بملف واحد اسمه `crypto/config.json`. انسخ الملف النموذجي وعدّل الأرقام حسب قواعدك أو قواعد شركة التحدي.

---

## Account · الحساب

| key | default | meaning | المعنى |
| --- | --- | --- | --- |
| `account_size` | `2500` | Starting balance in USDT | رصيد البداية بالـ USDT |
| `paper` | `true` | Demo / paper account. Shown on every ticket | حساب تجريبي، يظهر على كل تذكرة |

## Per trade · لكل صفقة

| key | default | meaning | المعنى |
| --- | --- | --- | --- |
| `risk_per_trade_pct` | `1` | % of balance to lose at the stop, used for sizing | نسبة الخسارة عند الوقف، تُستعمل لحساب الحجم |
| `max_risk_per_trade_pct` | `1` | Hard cap; a trade above it is blocked | الحد الأعلى، أي صفقة أكثر منه تنرفض |
| `stop_loss_required` | `true` | Every trade must have a stop | الوقف إجباري بكل صفقة |
| `min_rr` | `1.5` | Minimum reward:risk to the first target | أقل نسبة عائد للمخاطرة للهدف الأول |
| `max_leverage` | `10` | Highest leverage allowed | أعلى رافعة مسموحة |
| `default_leverage` | `5` | Used when a trade gives none | الرافعة الافتراضية |
| `max_notional_usd` | `0` | Largest position size in USDT (`0` = no cap) | أكبر حجم صفقة بالدولار (0 = بدون حد) |
| `allow_short` | `true` | Allow short trades | السماح بالشورت |
| `allowed_symbols` | `[]` | If not empty, only these symbols | إذا مو فارغة، بس هاي العملات |
| `blocked_symbols` | `[]` | Never trade these | عملات ممنوعة |

## Account limits · حدود الحساب

| key | default | meaning | المعنى |
| --- | --- | --- | --- |
| `max_open_positions` | `3` | Open trades at the same time | عدد الصفقات المفتوحة بنفس الوقت |
| `max_total_open_risk_pct` | `3` | Sum of all open risk, % of balance | مجموع مخاطرة كل الصفقات المفتوحة |
| `max_trades_per_day` | `10` | New trades per day | عدد الصفقات باليوم |

## Prop firm · شركة التحدي

Fill these from your firm's rules page. When a rule is unclear, choose the stricter reading.

املأها من صفحة قواعد الشركة. إذا القاعدة مو واضحة، اختار التفسير الأشد.

| key | default | meaning | المعنى |
| --- | --- | --- | --- |
| `daily_loss_limit_pct` | `5` | Daily loss limit | حد الخسارة اليومية |
| `daily_loss_base` | `start_of_day` | `start_of_day` = from the day's opening balance, `initial` = from the starting balance | تنحسب من رصيد بداية اليوم أو من رصيد البداية |
| `day_reset_utc` | `00:00` | When the firm's day resets, in UTC (Baghdad = UTC+3) | وقت تصفير اليوم بتوقيت UTC (بغداد +3) |
| `max_drawdown_pct` | `10` | Maximum loss allowed on the account | أقصى خسارة مسموحة بالحساب |
| `drawdown_type` | `static` | `static` = from the start, `trailing` = from the highest balance | ثابت من البداية أو متحرك من أعلى رصيد |
| `trailing_locks_at_initial` | `false` | Trailing floor stops rising at the starting balance | الحد المتحرك يوقف عند رصيد البداية |
| `profit_target_pct` | `10` | Profit target of the phase | هدف الربح للمرحلة |
| `min_trading_days` | `0` | Minimum trading days | أقل عدد أيام تداول |

## Costs · التكاليف

| key | default | meaning | المعنى |
| --- | --- | --- | --- |
| `taker_fee_pct` | `0.05` | Taker fee per side, % | رسوم التنفيذ لكل جهة |
| `maintenance_margin_pct` | `0.5` | Maintenance margin rate, for the liquidation estimate | نسبة الهامش للحفاظ، لتقدير سعر التصفية |

---

## Files the tools write · الملفات

| file | written by | content |
| --- | --- | --- |
| `crypto/plan.json` | crypto-plan | planned trades |
| `crypto/journal.json` | crypto-journal | every trade, open and closed |
| `crypto/state/risk.json` | crypto-risk | the last PASS / BLOCK verdicts |
| `crypto/spot.json`, `prices.json`, `targets.json` | you / crypto-rebalance | spot holdings, prices, target weights |

### `plan.json`

```json
{
  "orders": [
    {"symbol": "ZECUSDT", "side": "short", "entry": 520, "stop": 545,
     "targets": [470, 440], "leverage": 5, "type": "limit"}
  ]
}
```

Leave `qty` out and the risk check sizes the trade from `risk_per_trade_pct`,
capped by the daily and drawdown room left.

### `journal.json`

```json
{
  "trades": [
    {"id": 1, "symbol": "BTCUSDT", "side": "short", "entry": 97000, "stop": 98200,
     "qty": 0.02, "leverage": 5, "opened": "2026-11-13T06:00:00Z",
     "status": "closed", "exit": 95500, "closed": "2026-11-13T09:30:00Z",
     "fees": 3.85, "pnl_usd": 26.15, "initial_risk_usd": 25.95}
  ]
}
```

Times are UTC. Use `journal.py` rather than editing by hand.
