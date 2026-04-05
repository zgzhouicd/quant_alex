# -*- coding: utf-8 -*-
"""Storage/repository tests for minute bars and signals."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from src.config import Config
from src.repositories.intraday_repo import IntradayRepository
from src.storage import DatabaseManager


class IntradayRepositoryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.db_path = self.data_dir / "intraday_repo_test.db"
        self.env_path.write_text(
            "\n".join(
                [
                    "STOCK_LIST=AAPL",
                    "GEMINI_API_KEY=test",
                    f"DATABASE_PATH={self.db_path}",
                ]
            ) + "\n",
            encoding="utf-8",
        )
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.db_path)
        Config.reset_instance()
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()
        self.repo = IntradayRepository(self.db)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def test_save_and_load_intraday_bars_and_signal(self) -> None:
        base = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
        df = pd.DataFrame(
            [
                {
                    "timestamp": base + timedelta(minutes=i),
                    "open": 100 + i,
                    "high": 101 + i,
                    "low": 99 + i,
                    "close": 100.5 + i,
                    "volume": 1000 + i,
                    "amount": (100.5 + i) * (1000 + i),
                    "pct_chg": 0.1,
                    "interval": "1m",
                }
                for i in range(3)
            ]
        )

        saved = self.repo.save_bars(df, code="AAPL", interval="1m", data_source="test")
        self.assertEqual(saved, 3)

        bars = self.repo.get_bars(code="AAPL", interval="1m")
        self.assertEqual(len(bars), 3)
        self.assertEqual(bars[-1].code, "AAPL")

        self.repo.upsert_signal(
            {
                "code": "AAPL",
                "interval": "1m",
                "bar_start": bars[-1].bar_start,
                "signal": "long",
                "confidence": 0.8,
                "setup": "test_setup",
                "invalidation": 99.0,
                "last_price": 102.5,
                "vwap_session": 101.0,
                "ema_fast": 102.0,
                "ema_slow": 101.5,
                "macd": 0.5,
                "macd_signal": 0.2,
                "rsi": 61.0,
                "volume_ratio": 1.2,
                "opening_range_high": 101.0,
                "opening_range_low": 99.0,
                "recent_high": 103.0,
                "recent_low": 98.5,
                "reasons": ["价格位于会话 VWAP 上方"],
                "payload": {"engine": "test"},
            }
        )
        latest = self.repo.get_latest_signal(code="AAPL", interval="1m")
        self.assertIsNotNone(latest)
        self.assertEqual(latest["signal"], "long")
        self.assertEqual(latest["payload"]["engine"], "test")


if __name__ == "__main__":
    unittest.main()
