# -*- coding: utf-8 -*-
"""Tests for Binance public spot klines (intraday) — no network (mocked)."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch


def _fake_kline_row(open_ms: int, o: float, h: float, low: float, c: float, vol: float) -> list:
    return [open_ms, str(o), str(h), str(low), str(c), str(vol), open_ms + 59_999, "0", 0, "0", "0", "0"]


class TestBinanceSpotSymbol(unittest.TestCase):
    def test_btc_usdt_compact(self):
        from data_provider.binance_public_fetcher import binance_spot_symbol_for_intraday

        self.assertEqual(binance_spot_symbol_for_intraday("BTCUSDT"), "BTCUSDT")

    def test_btc_dash_usd(self):
        from data_provider.binance_public_fetcher import binance_spot_symbol_for_intraday

        self.assertEqual(binance_spot_symbol_for_intraday("BTC-USD"), "BTCUSDT")

    def test_aapl_not_crypto(self):
        from data_provider.binance_public_fetcher import binance_spot_symbol_for_intraday

        self.assertIsNone(binance_spot_symbol_for_intraday("AAPL"))


class TestBinanceIntradayMocked(unittest.TestCase):
    @patch("data_provider.binance_public_fetcher.urlopen")
    def test_get_intraday_parses_and_trims_window(self, mock_urlopen):
        from data_provider.binance_public_fetcher import BinancePublicFetcher

        # Two 1m bars, 60s apart; lookback=2 minutes should keep both anchored on max ts
        t0 = 1_700_000_000_000
        t1 = t0 + 60_000
        payload = json.dumps(
            [
                _fake_kline_row(t0, 1, 1, 1, 1, 10),
                _fake_kline_row(t1, 2, 2, 2, 2, 20),
            ]
        )
        mock_resp = MagicMock()
        mock_resp.read.return_value = payload.encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        fetcher = BinancePublicFetcher()
        df = fetcher.get_intraday_data("BTCUSDT", interval="1m", lookback_minutes=2)

        self.assertEqual(len(df), 2)
        self.assertIn("timestamp", df.columns)
        self.assertEqual(df["interval"].iloc[0], "1m")
        mock_urlopen.assert_called_once()

    @patch("data_provider.binance_public_fetcher.urlopen")
    def test_unsupported_interval_raises(self, mock_urlopen):
        from data_provider.binance_public_fetcher import BinancePublicFetcher
        from data_provider.base import DataFetchError

        fetcher = BinancePublicFetcher()
        with self.assertRaises(DataFetchError) as ctx:
            fetcher.get_intraday_data("BTCUSDT", interval="2m", lookback_minutes=60)
        self.assertIn("不支持", str(ctx.exception))
        mock_urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
