import csv
import datetime as dt
import importlib.util
import json
import os
import random
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG_NAME = "config.example.json"


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


bt = load("crypto-backtest/backtest.py", "backtest")
sim = load("crypto-prop/simulate.py", "simulate")
imp = load("crypto-journal/import_csv.py", "import_csv")
rev = load("crypto-journal/review.py", "review")
risk = load("crypto-risk/check.py", "check2")
with open(os.path.join(ROOT, CFG_NAME)) as f:
    CFG = json.load(f)
NOW = dt.datetime(2026, 11, 13, 9, 0, tzinfo=dt.timezone.utc)


def candles(n=400, drift=0.0, seed=1):
    rng, p, out = random.Random(seed), 100.0, []
    for i in range(n):
        o = p
        c = o * (1 + drift + rng.gauss(0, 0.01))
        out.append({"t": i, "o": o, "h": max(o, c) * 1.003, "l": min(o, c) * 0.997, "c": c})
        p = c
    return out


class TestBacktest(unittest.TestCase):
    def test_indicators(self):
        self.assertEqual(bt.ema([1, 1, 1, 1], 2)[-1], 1)
        r = bt.rsi([float(i) for i in range(1, 40)])
        self.assertEqual(r[-1], 100.0)
        self.assertIsNone(bt.atr(candles(20))[5])

    def test_stop_counted_first_and_r_bounds(self):
        trades = bt.run(candles(600), "breakout", rr=2.0, fee_pct=0.0)
        self.assertTrue(trades)
        for t in trades:
            self.assertIn(t["why"], ("stop", "target"))
            self.assertAlmostEqual(t["r"], -1.0 if t["why"] == "stop" else 2.0, places=2)

    def test_uptrend_long_breakout_positive(self):
        s = bt.summarize(bt.run(candles(800, drift=0.004), "breakout", side="long"))
        self.assertGreater(s["expectancy_r"], 0)

    def test_side_filter_and_small_sample_warning(self):
        tr = bt.run(candles(120), "ema-cross", side="long", fast=5, slow=10)
        self.assertTrue(all(t["side"] == "long" for t in tr))
        self.assertTrue(any("too few" in w for w in bt.summarize(tr[:3])["warnings"]))

    def test_load_csv_and_json(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "c.csv")
        with open(p, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Time", "Open", "High", "Low", "Close"])
            w.writerow([2, 2, 3, 1, 2])
            w.writerow([1, 1, 2, 1, 2])
        self.assertEqual([c["t"] for c in bt.load_candles(p)], ["1", "2"])
        q = os.path.join(d, "c.json")
        with open(q, "w") as f:
            json.dump({"data": [{"t": 1, "o": "1", "h": "2", "l": "1", "c": "2", "v": "5"}]}, f)
        self.assertEqual(bt.load_candles(q)[0]["c"], 2.0)


class TestSimulate(unittest.TestCase):
    def test_no_edge_rarely_passes_and_good_edge_often(self):
        bad = sim.simulate(CFG, lambda r: 1.0 if r.random() < 0.3 else -1.0, [1.0], runs=400)[0]
        good = sim.simulate(CFG, lambda r: 2.0 if r.random() < 0.55 else -1.0, [1.0], runs=400)[0]
        self.assertLess(bad["raw"]["pass_pct"], 10)
        self.assertGreater(good["raw"]["pass_pct"], 80)

    def test_guard_never_breaks_a_rule(self):
        row = sim.simulate(CFG, lambda r: 2.0 if r.random() < 0.3 else -1.0, [2.0], runs=400)[0]
        self.assertEqual(row["guarded"]["bust_pct"], 0)
        self.assertGreater(row["raw"]["bust_pct"], 0)

    def test_percentages_sum(self):
        m = sim.simulate(CFG, lambda r: 1.5 if r.random() < 0.5 else -1.0, [1.0], runs=300)[0]["guarded"]
        self.assertAlmostEqual(m["pass_pct"] + m["bust_pct"] + m["stuck_pct"] + m["timeout_pct"], 100, delta=0.3)


class TestImport(unittest.TestCase):
    def write(self, header, rows):
        p = os.path.join(tempfile.mkdtemp(), "h.csv")
        with open(p, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
        return p

    def test_detects_columns_and_timezone(self):
        p = self.write(["Contracts", "Side", "Avg Entry Price", "Avg Exit Price", "Closed Size", "Close Time", "Closed PnL"],
                       [["ZEC-USDT", "Sell", "520", "500", "2", "2026-11-13 12:00:00", "39.5"]])
        trades, errors, mapping = imp.read_trades(p, tz_offset=3)
        self.assertEqual(errors, [])
        t = trades[0]
        self.assertEqual((t["symbol"], t["side"], t["pnl_usd"]), ("ZECUSDT", "short", 39.5))
        self.assertEqual(t["closed"], "2026-11-13T09:00:00Z")

    def test_pnl_computed_and_closing_side(self):
        p = self.write(["symbol", "side", "entry price", "exit price", "qty", "time", "fee"],
                       [["BTCUSDT", "Sell", "100", "110", "1", "1763024400000", "0.2"]])
        t = imp.read_trades(p, closing_side=True)[0][0]
        self.assertEqual(t["side"], "long")
        self.assertAlmostEqual(t["pnl_usd"], 9.8)

    def test_missing_column_is_explained(self):
        p = self.write(["a", "b"], [["1", "2"]])
        with self.assertRaises(ValueError):
            imp.read_trades(p)


class TestReview(unittest.TestCase):
    def test_groups_and_fast_reentry(self):
        def tr(i, opened, closed, pnl, side="long"):
            return {"id": i, "symbol": "X", "side": side, "entry": 1, "exit": 1, "qty": 1, "status": "closed",
                    "opened": opened, "closed": closed, "pnl_usd": pnl, "tags": ["breakout"]}
        trades = [tr(1, "2026-11-09T06:00:00Z", "2026-11-09T06:30:00Z", -10),
                  tr(2, "2026-11-09T06:35:00Z", "2026-11-09T06:50:00Z", -12),
                  tr(3, "2026-11-10T10:00:00Z", "2026-11-10T15:00:00Z", 30, "short")]
        rv = rev.review(trades, tz_offset=3)
        self.assertEqual(rv["by_hour"]["09:00"]["trades"], 2)
        self.assertEqual(rv["by_weekday"]["Mon"]["net_usd"], -22)
        self.assertEqual(rv["sequence"]["fast_reentry_after_loss"]["trades"], 1)
        self.assertEqual(rv["by_tag"]["breakout"]["trades"], 3)
        self.assertEqual(rv["by_hold_time"]["4h-24h"]["trades"], 1)


class TestGuards(unittest.TestCase):
    ORDER = {"symbol": "ZECUSDT", "side": "short", "entry": 520, "stop": 545, "targets": [470], "leverage": 5}

    def loss(self, i, hour, minute=0):
        t = "2026-11-13T{:02d}:{:02d}:00Z".format(hour, minute)
        return {"id": i, "symbol": "BTCUSDT", "side": "long", "entry": 100, "exit": 99, "qty": 10, "stop": 99,
                "leverage": 2, "opened": t, "closed": t, "status": "closed", "pnl_usd": -10}

    def test_cooldown_after_two_losses(self):
        j = {"trades": [self.loss(1, 8, 0), self.loss(2, 8, 30)]}
        r = risk.check_orders(CFG, j, [self.ORDER], NOW)
        self.assertTrue(any("cooldown" in x for x in r[0]["reasons"]))
        later = NOW + dt.timedelta(hours=2)
        self.assertEqual(risk.check_orders(CFG, j, [self.ORDER], later)[0]["verdict"], "PASS")

    def test_max_losses_per_day(self):
        j = {"trades": [self.loss(1, 1), self.loss(2, 2), self.loss(3, 3)]}
        r = risk.check_orders(CFG, j, [self.ORDER], NOW)
        self.assertTrue(any("stop for today" in x for x in r[0]["reasons"]))

    def test_risk_cut_when_drawdown_half_used(self):
        big = dict(self.loss(1, 1), pnl_usd=-130, closed="2026-11-10T01:00:00Z", opened="2026-11-10T01:00:00Z")
        r = risk.check_orders(CFG, {"trades": [big]}, [self.ORDER], NOW)
        self.assertEqual(r[0]["verdict"], "PASS")
        self.assertAlmostEqual(r[0]["order"]["risk_usd"], 2370 * 0.01 * 0.5, places=1)

    def test_same_side_cap(self):
        open_short = {"id": 1, "symbol": "SOLUSDT", "side": "short", "entry": 200, "stop": 210, "qty": 4,
                      "leverage": 5, "opened": "2026-11-13T08:00:00Z", "status": "open"}
        r = risk.check_orders(CFG, {"trades": [open_short]}, [self.ORDER], NOW)
        self.assertTrue(any("same-direction" in x for x in r[0]["reasons"]))
        long_order = {"symbol": "ETHUSDT", "side": "long", "entry": 3400, "stop": 3300, "targets": [3600], "leverage": 5}
        self.assertEqual(risk.check_orders(CFG, {"trades": [open_short]}, [long_order], NOW)[0]["verdict"], "PASS")


if __name__ == "__main__":
    unittest.main()
