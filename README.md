# crypto-trade-skill

[![tests](https://github.com/devfn93/crypto-trade-skill/actions/workflows/tests.yml/badge.svg)](https://github.com/devfn93/crypto-trade-skill/actions/workflows/tests.yml)

[العربية](#بالعربي) · [English](#english)

Seven Claude skills for crypto traders (futures and spot). They test a strategy
on past data, plan a trade, size it from the money you are willing to lose,
check it against your own rules and your prop-firm limits, and show you where
your journal makes and loses money. **Claude never places an order: you do.**

Free, MIT, no signup, no API keys. The tools are plain Python 3 (standard library only,
tested on 3.12 and 3.13) that do arithmetic on files in a `crypto/` folder.

---

## بالعربي

مجموعة مهارات لـ Claude تساعد متداولين الكربتو، وخصوصاً تحديات شركات التمويل (Prop Firms). تسوي خطة للصفقة وتحسب حجمها من المبلغ اللي مستعد تخسره، وتفحصها على قواعدك وحدود التحدي، وتسجل صفقاتك وتطلع إحصائياتك.

**Claude ما ينفذ أي صفقة.** يطلعلك تذكرة جاهزة وانت تدخلها بمنصتك، والوقف يكون بنفس الأمر.

| المهارة | شنو تسوي |
| --- | --- |
| `/crypto-backtest` | تختبر الاستراتيجية على شموع قديمة قبل ما تخاطر بفلس: نسبة الربح، العائد المتوقع، أطول سلسلة خسائر |
| `/crypto-plan` | تحليل العملة (الاتجاه، الدعوم والمقاومات، ATR، الفوليوم، التمويل، الأخبار) وكتابة خطة: دخول، وقف، أهداف، ومتى تلغى الفكرة |
| `/crypto-size` | تحسب حجم الصفقة من نسبة المخاطرة ومسافة الوقف مع الرسوم، والمارجن، وسعر التصفية، وهل الوقف يضرب قبل التصفية |
| `/crypto-risk` | تفحص كل صفقة على قواعدك قبل ما تدخلها: الوقف إجباري، أقصى مخاطرة ورافعة، العائد للمخاطرة، الخسارة اليومية، الـ drawdown، استراحة إجبارية بعد الخسائر المتتالية، وحد للمخاطرة بنفس الاتجاه. النتيجة PASS أو BLOCK مع السبب |
| `/crypto-prop` | حالة حساب التحدي: الخسارة اليومية المستخدمة والمتبقية، الـ drawdown (ثابت أو متحرك)، التقدم للهدف، وأكثر مبلغ تكدر تخاطر بيه بالصفقة الجاية. وتحاكي آلاف التحديات حتى تختار أحسن نسبة مخاطرة |
| `/crypto-journal` | سجل الصفقات، واستيراد تاريخ الصفقات من ملف المنصة، ومراجعة تبين وين تربح ووين تخسر: حسب العملة والساعة واليوم ومدة الصفقة وبعد الخسارة |
| `/crypto-rebalance` | إعادة توازن محفظة السبوت حسب النسب اللي تحددها |

### طريقة الاستعمال

```
crypto-backtest -> crypto-prop -> crypto-plan -> crypto-size -> crypto-risk -> انت تدخل الصفقة -> crypto-journal
```

1. انسخ `config.example.json` إلى `crypto/config.json` واكتب قواعد تحديك من صفحة الشركة (حجم الحساب، الخسارة اليومية، الـ drawdown، الرافعة...).
2. قبل كل جلسة تداول اطلب: "استعمل crypto-prop وكلي شكد باقيلي اليوم".
3. للصفقة: "حلل ZEC على فريم الساعة وسويلي خطة"، وبعدها "افحصها بـ crypto-risk".
4. بعد ما تدخل الصفقة وتسكرها، سجلها بـ crypto-journal.

---

## English

| command | job |
| --- | --- |
| `/crypto-backtest` | Tests a rule (breakout, EMA cross, RSI) on past candles, fees included: expectancy in R, drawdown, losing streak, first half vs second half |
| `/crypto-plan` | Reads the market from live data (trend structure, levels, ATR, volume, funding, news) and writes a plan: entry, stop, targets, what cancels it |
| `/crypto-size` | Quantity from your risk and the stop distance, fees included; margin, the leverage really needed, liquidation estimate, stop-before-liquidation check |
| `/crypto-risk` | Checks every planned trade against your rules: stop required, max risk and leverage, reward:risk, margin, exposure, daily loss and drawdown room, a cooldown after losses, a same-direction (correlation) cap, smaller risk deep in drawdown. PASS or BLOCK with the reason, and a ticket |
| `/crypto-prop` | Prop-firm guard: daily loss used and left, static or trailing drawdown, profit target, trading days, and the most the next trade may risk. Simulates thousands of challenges to compare pass and bust rates per risk size |
| `/crypto-journal` | The trade log every tool reads; imports an exchange CSV; stats and a review by coin, side, hour, weekday, holding time and what happens after a loss |
| `/crypto-rebalance` | Brings a spot portfolio back to its target weights (USDT as cash), sells before buys |

### Install

In Claude (web, desktop, mobile): zip each `crypto-*` folder (the folder at the
root of the zip) and upload it in **Customize > Skills > + > Upload a skill**.

In Claude Code, as a plugin:

```
/plugin marketplace add devfn93/crypto-trade-skill
/plugin install crypto-trade-skill@crypto-trade-skill
```

Or copy the folders: `cp -r crypto-* ~/.claude/skills/`

### Flow

```
crypto-backtest -> crypto-prop -> crypto-plan -> crypto-size -> crypto-risk -> you place it -> crypto-journal
```

Copy `config.example.json` to `crypto/config.json` and fill in your rules. Every key is explained in [docs/configuration.md](docs/configuration.md).
Everything else lands in `crypto/`: `plan.json`, `journal.json`,
`state/risk.json`, and `spot.json` / `prices.json` / `targets.json` for
rebalancing.

### The tools

```bash
python3 crypto-size/size.py --side short --entry 97000 --stop 98200 --targets 95000 93000
python3 crypto-risk/check.py                    # PASS / BLOCK per planned trade + tickets
python3 crypto-prop/prop.py                     # challenge status, room left today
python3 crypto-journal/journal.py open --symbol ZECUSDT --side short --entry 520 --stop 545 --qty 0.97 --leverage 5
python3 crypto-journal/journal.py close --id 1 --exit 470
python3 crypto-journal/journal.py stats
python3 crypto-journal/import_csv.py history.csv --tz-offset 3 --dry-run   # exchange export -> journal
python3 crypto-journal/review.py                # where the money is made and lost
python3 crypto-backtest/backtest.py candles.csv --strategy breakout --rr 2
python3 crypto-prop/simulate.py --win-rate 45 --avg-win-r 2               # pass / bust odds per risk size
python3 crypto-rebalance/rebalance.py --band 5
python3 -m unittest discover -s tests -v       # offline tests
```

### Example

$2,500 demo challenge, 1% risk, 5% daily loss, 10% static drawdown, one losing
BTC short today:

```
PASS  #1 short ZECUSDT  risk $24.74
BLOCK  #2 short QNTUSDT  risk $24.74
      - leverage 20.0x is over your max 10x
      - reward:risk 1.43 is under your minimum 1.5
BLOCK  #3 long ETHUSDT
      - no stop loss (your rules require one on every trade)

TICKET 1 of 3  (PAPER/DEMO account) - you place this yourself
  SHORT ZECUSDT limit  qty 0.96898071  ~$503.87
  entry 520   stop 545   leverage 5.0x (isolated)
  targets 470, 440   (R:R to first 1.94)
  loss at stop $24.74   margin $100.77   liquidation ~621.4
```

## Fine print

**Not financial advice, and no promise of profit.** This is software that does
arithmetic on numbers you give it. It cannot see the future. A backtest or a
simulation describes the past and a model, not what will happen. Leveraged crypto can lose the whole account
quickly. Decide for yourself.

**No order is ever placed by Claude or by these tools.** There is no exchange
connection and no order code. Never give Claude, or anyone, your exchange API
keys, secrets or seed phrase.

**Your firm's rules are the final word.** Firms measure daily loss and
drawdown differently (balance vs equity, reset times, fees, funding). The tools
use closed trades plus the worst case of open trades to their stops; compare
with the firm's dashboard.

**Liquidation prices are estimates** for isolated, USDT-margined contracts.
Exchanges add tiers and fees; keep a margin of safety.

## Author

**Esraa Fadhil Naif** · [github.com/devfn93](https://github.com/devfn93)

MIT. See [LICENSE](LICENSE).
