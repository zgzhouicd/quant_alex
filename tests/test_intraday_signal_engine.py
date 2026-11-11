# -*- coding: utf-8 -*-
"""Tests for intraday signal engine and supporting service logic."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

import pandas as pd

from src.core.intraday_signal_engine import IntradaySignalEngine


class IntradaySignalEngineTestCase(unittest.TestCase):
    def test_analyze_generates_long_signal_with_vwap_and_momentum(self) -> None:
        base = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
        rows = []
        price = 100.0
        for i in range(40):
            close = price + 0.4
            rows.append(
                {
                    "timestamp": base + timedelta(minutes=i),
                    "open": price,
                    "high": close + 0.2,
                    "low": price - 0.1,
                    "close": close,
                    "volume": 1000 + i * 25,
                    "amount": (1000 + i * 25) * close,
                    "pct_chg": 0.1,
                    "interval": "1m",
                }
            )
            price = close

        df = pd.DataFrame(rows)
        engine = IntradaySignalEngine()
        result = engine.analyze(df, code="AAPL", interval="1m")

        self.assertEqual(result.signal, "long")
        self.assertGreater(result.vwap_session, 0)
        self.assertGreater(result.last_price, result.vwap_session)
        self.assertGreaterEqual(len(result.reasons), 4)

    def test_analyze_daily_interval_marks_payload_and_setup(self) -> None:
        base = datetime(2025, 1, 2, tzinfo=timezone.utc)
        rows = []
        price = 100.0
        for i in range(40):
            d = base + timedelta(days=i)
            close = price + 0.35
            rows.append(
                {
                    "timestamp": d,
                    "open": price,
                    "high": close + 0.15,
                    "low": price - 0.1,
                    "close": close,
                    "volume": 1_000_000 + i * 2000,
                    "amount": close * (1_000_000 + i * 2000),
                    "pct_chg": 0.15,
                    "interval": "1d",
                }
            )
            price = close

        df = pd.DataFrame(rows)
        engine = IntradaySignalEngine()
        result = engine.analyze(df, code="AAPL", interval="1d")

        self.assertEqual(result.payload.get("signal_timeframe"), "daily")
        self.assertTrue(result.setup.startswith("daily_") or "daily" in result.setup)


if __name__ == "__main__":
    unittest.main()
