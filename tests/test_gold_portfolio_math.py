import datetime as dt
from types import SimpleNamespace
from unittest.mock import patch
import unittest

import pandas as pd

import gold_portfolio_math as gpm


def make_snapshot(gold_usd_per_gram, gold_try_per_gram, usd_try, is_fallback=False):
    return SimpleNamespace(
        gold_usd_per_gram=gold_usd_per_gram,
        gold_try_per_gram=gold_try_per_gram,
        usd_try=usd_try,
        is_fallback=is_fallback,
    )


class PortfolioMathTests(unittest.TestCase):
    def test_prepare_portfolio_frame_normalizes_types(self):
        raw = pd.DataFrame(
            [
                {
                    "purchase_date": "2023-01-01",
                    "grams": "2.5",
                    "cost_try": "100.25",
                    "cost_usd": "5.10",
                },
                {
                    "purchase_date": "2023-01-02",
                    "grams": "3",
                    "cost_try": "200",
                    "cost_usd": "10",
                },
            ]
        )

        prepared = gpm.prepare_portfolio_frame(raw)

        self.assertEqual(prepared.columns.tolist(), ["Date", "Grams", "Cost (TRY)", "Cost (USD)"])
        self.assertEqual(prepared.loc[0, "Date"], dt.date(2023, 1, 1))
        self.assertEqual(prepared.loc[1, "Date"], dt.date(2023, 1, 2))
        self.assertAlmostEqual(prepared.loc[0, "Grams"], 2.5)
        self.assertAlmostEqual(prepared.loc[1, "Grams"], 3.0)
        self.assertAlmostEqual(prepared.loc[0, "Cost (TRY)"], 100.25)
        self.assertAlmostEqual(prepared.loc[0, "Cost (USD)"], 5.10)

    def test_prepare_portfolio_frame_keeps_empty_frame_copy(self):
        raw = pd.DataFrame()

        prepared = gpm.prepare_portfolio_frame(raw)

        self.assertTrue(prepared.empty)
        self.assertIsNot(prepared, raw)

    def test_build_portfolio_analysis_uses_purchase_day_snapshots_and_sell_spread(self):
        raw = pd.DataFrame(
            [
                {
                    "purchase_date": "2023-01-01",
                    "grams": 2,
                    "cost_try": 100,
                    "cost_usd": 5,
                },
                {
                    "purchase_date": "2023-01-02",
                    "grams": 3,
                    "cost_try": 200,
                    "cost_usd": 10,
                },
            ]
        )

        snapshot_map = {
            dt.date(2023, 1, 1): make_snapshot(50.0, 1500.0, 30.0, False),
            dt.date(2023, 1, 2): make_snapshot(60.0, 1800.0, 30.0, True),
        }
        live_snapshot = make_snapshot(100.0, 3000.0, 30.0, False)

        with patch("gold_portfolio_math.fetch_market_snapshot_for_date") as mock_fetch:
            mock_fetch.side_effect = lambda target_date: snapshot_map[target_date]
            analysis_df, fallback_used = gpm.build_portfolio_analysis(raw, 10.0, live_snapshot)

        self.assertTrue(fallback_used)
        self.assertAlmostEqual(analysis_df.loc[0, "Purchase Price / Gram (USD)"], 50.0)
        self.assertAlmostEqual(analysis_df.loc[0, "Purchase Price / Gram (TRY)"], 1500.0)
        self.assertAlmostEqual(analysis_df.loc[0, "Purchase USD/TRY"], 30.0)
        self.assertAlmostEqual(analysis_df.loc[1, "Purchase Price / Gram (USD)"], 60.0)
        self.assertAlmostEqual(analysis_df.loc[1, "Purchase Price / Gram (TRY)"], 1800.0)

        self.assertAlmostEqual(analysis_df.loc[0, "Sell Today Price / Gram (USD)"], 90.0)
        self.assertAlmostEqual(analysis_df.loc[0, "Sell Today Price / Gram (TRY)"], 2700.0)
        self.assertAlmostEqual(analysis_df.loc[0, "Sell Today Value (USD)"], 180.0)
        self.assertAlmostEqual(analysis_df.loc[0, "Sell Today Value (TRY)"], 5400.0)
        self.assertAlmostEqual(analysis_df.loc[0, "Projected P/L (USD)"], 175.0)
        self.assertAlmostEqual(analysis_df.loc[0, "Projected P/L (TRY)"], 5300.0)

        self.assertAlmostEqual(analysis_df.loc[1, "Sell Today Value (USD)"], 270.0)
        self.assertAlmostEqual(analysis_df.loc[1, "Sell Today Value (TRY)"], 8100.0)
        self.assertAlmostEqual(analysis_df.loc[1, "Projected P/L (USD)"], 260.0)
        self.assertAlmostEqual(analysis_df.loc[1, "Projected P/L (TRY)"], 7900.0)

    def test_currency_config_and_money_formatting(self):
        usd_cfg = gpm.get_display_currency_config("USD")
        self.assertEqual(usd_cfg["code"], "USD")
        self.assertEqual(usd_cfg["purchase_cost_col"], "Cost (USD)")
        self.assertEqual(usd_cfg["sell_value_col"], "Sell Today Value (USD)")

        try_cfg = gpm.get_display_currency_config("TRY")
        self.assertEqual(try_cfg["code"], "TRY")
        self.assertEqual(try_cfg["purchase_cost_col"], "Cost (TRY)")
        self.assertEqual(try_cfg["sell_value_col"], "Sell Today Value (TRY)")

        fallback_cfg = gpm.get_display_currency_config("GBP")
        self.assertEqual(fallback_cfg["code"], "TRY")

        self.assertEqual(gpm.format_money(1234.5, "USD"), "$1,234.50")
        self.assertEqual(gpm.format_money(1234.5, "TRY"), "1,234.50 TL")
        self.assertEqual(gpm.format_money(float("nan"), "USD"), "")

