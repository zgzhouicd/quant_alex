# -*- coding: utf-8 -*-
"""Unit tests for YfinanceFetcher._convert_stock_code (futures / crypto / PERP)."""

import os
import sys
import unittest
from unittest.mock import MagicMock

if "fake_useragent" not in sys.modules:
    sys.modules["fake_useragent"] = MagicMock()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestYfinanceConvertStockCode(unittest.TestCase):
    def setUp(self):
        from data_provider.yfinance_fetcher import YfinanceFetcher

        self.fetcher = YfinanceFetcher()

    def test_us_index_future_symbol_passthrough(self):
        self.assertEqual(self.fetcher._convert_stock_code("ES=F"), "ES=F")

    def test_crypto_usdt_to_yahoo_dash(self):
        self.assertEqual(self.fetcher._convert_stock_code("BTCUSDT"), "BTC-USD")

    def test_crypto_perp_suffix_stripped(self):
        self.assertEqual(self.fetcher._convert_stock_code("BTCUSDT-PERP"), "BTC-USD")

    def test_ethbtc_cross(self):
        self.assertEqual(self.fetcher._convert_stock_code("ETHBTC"), "ETH-BTC")

    def test_btc_usd_compact(self):
        self.assertEqual(self.fetcher._convert_stock_code("BTCUSD"), "BTC-USD")

    def test_yahoo_dash_crypto_passthrough(self):
        self.assertEqual(self.fetcher._convert_stock_code("BTC-USD"), "BTC-USD")


if __name__ == "__main__":
    unittest.main()
