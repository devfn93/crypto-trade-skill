import importlib.util
import json
import os
import unittest
import datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


size = load("crypto-size/size.py", "size")
risk = load("crypto-risk/check.py", "check")
prop = load("crypto-prop/prop.py", "prop")
journal = load("crypto-journal/journal.py", "journal")
reb = load("crypto-rebalance/rebalance.py", "rebalance")

with open(os.path.join(ROOT, "config.example.json")) as f:
    CFG = json.load(f)
NOW = dt.datetime(2026, 11, 13, 9, 0, tzinfo=dt.timezone.utc)
LOSS = {"trades": [{"id": 1, "symbol": "BTCUSDT", "side": "short", "entry": 97000, "stop": 98200,
                    "qty": 0.02, "leverage": 5, "opened": "2026-11-13T06:00:00Z",
                    "closed": "2026-11-13T07:00:00Z", "exit": 98200, "status": "closed"}]}


class TestSize(unittest.TestCase):
    def test_risk_includes_fees(self):
        r = size.size_trade(2500, 1, "short", 97000, 98200, leverage=5)
        self.assertAlmostEqual(r["loss_at_stop_usd"], 25.0, places=2)
        self.assertTrue(r["stop_before_liquidation"])

    def test_liquidation_formula(self):
        self.assertAlmostEqual(size.liquidation_price("long", 100, 10, 0.5), 90.5)
        self.assertAlmostEqual(size.liquidation_price("short", 100, 10, 0.5), 109.5)
        self.assertIsNone(size.liquidation_price("long", 100, 1, 0.5))

    def test_stop_after_liquidation_flagged(self):
        r = size.size_trade(1000, 1, "long", 100, 90, leverage=20)
        self.assertFalse(r["stop_before_liquidation"])

    def test_wrong_side_stop(self):
        with self.assertRaises(ValueError):
            size.size_trade(1000, 1, "long", 100, 101)


class TestProp(unittest.TestCase):
    def test_daily_room_after_loss(self):
        s = prop.ledger(CFG, LOSS, NOW)
        self.assertAlmostEqual(s["today_realized"], -25.95, places=2)
        self.assertAlmostEqual(s["daily_limit"], 125.0)
        self.assertAlmostEqual(s["daily_room"], 99.05, places=2)
        self.assertAlmostEqual(s["drawdown_floor"], 2250.0)

    def test_loss_yesterday_not_counted_today(self):
        s = prop.ledger(CFG, LOSS, NOW + dt.timedelta(days=1))
        self.assertEqual(s["today_realized"], 0)

    def test_trailing_floor_rises(self):
        cfg = dict(CFG, drawdown_type="trailing")
        win = {"trades": [{"id": 1, "symbol": "X", "side": "long", "entry": 100, "exit": 110, "qty": 10,
                           "stop": 95, "opened": "2026-11-12T01:00:00Z", "closed": "2026-11-12T02:00:00Z",
                           "status": "closed", "fees": 0}]}
        s = prop.ledger(cfg, win, NOW)
        self.assertAlmostEqual(s["drawdown_floor"], 2600 * 0.9)

    def test_ledger_code_identical(self):
        def block(path):
            src = open(os.path.join(ROOT, path)).read()
            a = src.index("def parse_time")
            return src[a:src.index("# ---- end ledger ----")]
        self.assertEqual(block("crypto-prop/prop.py"), block("crypto-risk/check.py"))


class TestRisk(unittest.TestCase):
    def run_orders(self, orders, j=None, cfg=None):
        return risk.check_orders(cfg or CFG, j or {"trades": []}, orders, NOW)

    def test_pass_and_sized(self):
        r = self.run_orders([{"symbol": "ZECUSDT", "side": "short", "entry": 520, "stop": 545,
                              "targets": [470], "leverage": 5}])
        self.assertEqual(r[0]["verdict"], "PASS")
        self.assertAlmostEqual(r[0]["order"]["risk_usd"], 25.0, places=1)

    def test_no_stop_blocked(self):
        r = self.run_orders([{"symbol": "ETHUSDT", "side": "long", "entry": 3400}])
        self.assertEqual(r[0]["verdict"], "BLOCK")

    def test_leverage_and_rr(self):
        r = self.run_orders([{"symbol": "QNTUSDT", "side": "short", "entry": 110, "stop": 114,
                              "targets": [104], "leverage": 20}])
        txt = " ".join(r[0]["reasons"])
        self.assertIn("leverage", txt)
        self.assertIn("reward:risk", txt)

    def test_daily_room_blocks_big_trade(self):
        r = self.run_orders([{"symbol": "SOLUSDT", "side": "long", "entry": 200, "stop": 190,
                              "qty": 12, "targets": [240], "leverage": 5}],
                            j=LOSS, cfg=dict(CFG, max_risk_per_trade_pct=50, max_total_open_risk_pct=50))
        self.assertTrue(any("daily loss room" in x for x in r[0]["reasons"]))

    def test_batch_duplicate(self):
        o = {"symbol": "ZECUSDT", "side": "short", "entry": 520, "stop": 545, "targets": [470], "leverage": 5}
        r = self.run_orders([o, dict(o)])
        self.assertEqual([x["verdict"] for x in r], ["PASS", "BLOCK"])


class TestJournal(unittest.TestCase):
    def test_stats(self):
        trades = [
            {"symbol": "A", "side": "long", "entry": 10, "exit": 12, "qty": 10, "fees": 0, "status": "closed", "initial_risk_usd": 10},
            {"symbol": "A", "side": "short", "entry": 10, "exit": 11, "qty": 10, "fees": 0, "status": "closed", "initial_risk_usd": 10},
        ]
        s = journal.stats(trades, 0.05)
        self.assertEqual(s["net_pnl_usd"], 10)
        self.assertEqual(s["win_rate_pct"], 50.0)
        self.assertEqual(s["profit_factor"], 2.0)
        self.assertEqual(s["avg_r"], 0.5)


class TestRebalance(unittest.TestCase):
    def test_trades(self):
        r = reb.rebalance({"holdings": {"BTC": 0.01, "ETH": 0.5}, "cash_usdt": 300},
                          {"BTC": 97000, "ETH": 3400}, {"BTC": 50, "ETH": 30, "USDT": 20})
        self.assertEqual([t["side"] for t in r["trades"]], ["sell", "buy"])
        self.assertEqual(r["trades"][0]["asset"], "ETH")


if __name__ == "__main__":
    unittest.main()
