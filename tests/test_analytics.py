"""Unit tests for option yield formulas, Black-Scholes IV/Greeks, and technical indicators."""

import unittest
import numpy as np
import pandas as pd

from screener.analytics import (
    bs_price,
    calculate_annualized_cc_yield,
    calculate_annualized_csp_yield,
    compute_option_greeks,
    compute_technicals_and_hv,
    select_otm_call,
    select_otm_put,
    solve_implied_volatility,
)


class TestOptionYieldAnalytics(unittest.TestCase):
    def test_csp_yield_calculation(self):
        raw_pct, ann_pct = calculate_annualized_csp_yield(premium=2.0, strike=100.0, dte=30)
        self.assertAlmostEqual(raw_pct, 2.00)
        self.assertAlmostEqual(ann_pct, 24.33)

    def test_cc_yield_calculation(self):
        raw_pct, ann_pct, if_called_pct = calculate_annualized_cc_yield(
            premium=2.5, strike=105.0, spot_price=100.0, dte=30
        )
        self.assertAlmostEqual(raw_pct, 2.50)
        self.assertAlmostEqual(ann_pct, 30.42)
        self.assertAlmostEqual(if_called_pct, 91.25)

    def test_black_scholes_iv_and_greeks(self):
        spot = 100.0
        strike = 95.0
        t_years = 30.0 / 365.0
        true_iv = 0.30
        put_price = bs_price(spot, strike, t_years, true_iv, option_type="put")
        solved_iv = solve_implied_volatility(put_price, spot, strike, t_years, option_type="put")
        self.assertAlmostEqual(solved_iv, true_iv, places=2)

        delta, pop_pct = compute_option_greeks(spot, strike, t_years, solved_iv, option_type="put")
        self.assertTrue(-0.45 < delta < -0.10)
        self.assertTrue(60.0 < pop_pct < 90.0)

    def test_technicals_and_hv(self):
        rng = np.random.default_rng(42)
        rets = rng.normal(0.0005, 0.015, size=252)
        prices = 100.0 * np.exp(np.cumsum(rets))
        df = pd.DataFrame({"Close": prices})
        tech = compute_technicals_and_hv(df)
        self.assertTrue(0.0 <= tech["rsi_14"] <= 100.0)
        self.assertTrue(tech["hv_30d_pct"] > 5.0)
        self.assertTrue(0.0 <= tech["vol_rank_52w_pct"] <= 100.0)

    def test_select_otm_put_and_call(self):
        puts = pd.DataFrame(
            [
                {"strike": 90.0, "bid": 1.0, "ask": 1.2, "lastPrice": 1.1},
                {"strike": 95.0, "bid": 2.0, "ask": 2.2, "lastPrice": 2.1},
                {"strike": 100.0, "bid": 4.0, "ask": 4.2, "lastPrice": 4.1},
            ]
        )
        calls = pd.DataFrame(
            [
                {"strike": 100.0, "bid": 4.0, "ask": 4.2, "lastPrice": 4.1},
                {"strike": 105.0, "bid": 2.0, "ask": 2.4, "lastPrice": 2.2},
                {"strike": 110.0, "bid": 0.8, "ask": 1.0, "lastPrice": 0.9},
            ]
        )
        put_row = select_otm_put(puts, spot_price=100.0, target_otm_pct=0.05)
        call_row = select_otm_call(calls, spot_price=100.0, target_otm_pct=0.05)

        self.assertEqual(put_row["strike"], 95.0)
        self.assertAlmostEqual(put_row["premium"], 2.10)
        self.assertEqual(call_row["strike"], 105.0)
        self.assertAlmostEqual(call_row["premium"], 2.20)


if __name__ == "__main__":
    unittest.main()
