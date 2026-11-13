# crypto-trade-skill

[العربية](#بالعربي) · [English](#english)

Six Claude skills for crypto traders. They plan a trade, size it from the money
you are willing to lose, check it against your own rules and your prop-firm
limits, and keep your journal. **Claude never places an order: you do.**

Free, MIT, no signup, no API keys. The tools are plain Python (standard library,
3.8+) that do arithmetic on files in a `crypto/` folder.

---

## بالعربي

مجموعة مهارات لـ Claude تساعد متداولين الكربتو، وخصوصاً تحديات شركات التمويل (Prop Firms). تسوي خطة للصفقة وتحسب حجمها من المبلغ اللي مستعد تخسره، وتفحصها على قواعدك وحدود التحدي، وتسجل صفقاتك وتطلع إحصائياتك.

**Claude ما ينفذ أي صفقة.** يطلعلك تذكرة جاهزة وانت تدخلها بمنصتك، والوقف يكون بنفس الأمر.

| المهارة | شنو تسوي |
| --- | --- |
| `/crypto-plan` | تحليل العملة (الاتجاه، الدعوم والمقاومات، ATR، الفوليوم، التمويل، الأخبار) وكتابة خطة: دخول، وقف، أهداف، ومتى تلغى الفكرة |
| `/crypto-size` | تحسب حجم الصفقة من نسبة المخاطرة ومسافة الوقف مع الرسوم، والمارجن، وسعر التصفية، وهل الوقف يضرب قبل التصفية |
| `/crypto-risk` | تفحص كل صفقة على قواعدك قبل ما تدخلها: الوقف إجباري، أقصى مخاطرة ورافعة، العائد للمخاطرة، الخسارة اليومية، الـ drawdown. النتيجة PASS أو BLOCK مع السبب |
| `/crypto-prop` | حالة حساب التحدي: الخسارة اليومية المستخدمة والمتبقية، الـ drawdown (ثابت أو متحرك)، التقدم للهدف، وأكثر مبلغ تكدر تخاطر بيه بالصفقة الجاية |
| `/crypto-journal` | سجل الصفقات والإحصائيات: نسبة الربح، معامل الربح، متوسط R، أطول سلسلة خسائر، والربح حسب العملة والاتجاه |
| `/crypto-rebalance` | إعادة توازن محفظة السبوت حسب النسب اللي تحددها |

### طريقة الاستعمال

```
crypto-prop -> crypto-plan -> crypto-size -> crypto-risk -> انت تدخل الصفقة -> crypto-journal
```

1. انسخ `config.example.json` إلى `crypto/config.json` واكتب قواعد تحديك من صفحة الشركة (حجم الحساب، الخسارة اليومية، الـ drawdown، الرافعة...).
2. قبل كل جلسة تداول اطلب: "استعمل crypto-prop وكلي شكد باقيلي اليوم".
3. للصفقة: "حلل ZEC على فريم الساعة وسويلي خطة"، وبعدها "افحصها بـ crypto-risk".
4. بعد ما تدخل الصفقة وتسكرها، سجلها بـ crypto-journal.

---

## English

| command | job |
| --- | --- |
| `/crypto-plan` | Reads the market from live data (trend structure, levels, ATR, volume, funding, news) and writes a plan: entry, stop, targets, what cancels it |
| `/crypto-size` | Quantity from your risk and the stop distance, fees included; margin, the leverage really needed, liquidation estimate, stop-before-liquidation check |
| `/crypto-risk` | Checks every planned trade against your rules: stop required, max risk and leverage, reward:risk, margin, exposure, daily loss and drawdown room. PASS or BLOCK with the reason, and a ticket |
| `/crypto-prop` | Prop-firm guard: daily loss used and left, static or trailing drawdown, profit target, trading days, and the most the next trade may risk |
| `/crypto-journal` | The trade log every tool reads, plus stats: win rate, profit factor, expectancy, average R, losing streak, P&L by coin and side |
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
crypto-prop -> crypto-plan -> crypto-size -> crypto-risk -> you place it -> crypto-journal
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

**Not financial advice.** This is software that does arithmetic on numbers you
give it. It cannot see the future. Leveraged crypto can lose the whole account
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
