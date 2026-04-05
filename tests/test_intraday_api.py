# -*- coding: utf-8 -*-
"""API tests for intraday signal and paper trading endpoints."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
from fastapi.testclient import TestClient

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from api.app import create_app
from src.config import Config
from src.storage import DatabaseManager


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


class IntradayApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.db_path = self.data_dir / "intraday_api_test.db"
        self.env_path.write_text(
            "\n".join(
                [
                    "STOCK_LIST=AAPL",
                    "GEMINI_API_KEY=test",
                    "ADMIN_AUTH_ENABLED=false",
                    f"DATABASE_PATH={self.db_path}",
                ]
            ) + "\n",
            encoding="utf-8",
        )
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.db_path)
        Config.reset_instance()
        DatabaseManager.reset_instance()
        app = create_app(static_dir=self.data_dir / "empty-static")
        self.client = TestClient(app)
        self.db = DatabaseManager.get_instance()
        self._seed_intraday_bars("AAPL")

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def _seed_intraday_bars(self, symbol: str) -> None:
        base = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
        price = 100.0
        rows = []
        for i in range(40):
            close = price + 0.35
            rows.append(
                {
                    "timestamp": base + timedelta(minutes=i),
                    "open": price,
                    "high": close + 0.1,
                    "low": price - 0.1,
                    "close": close,
                    "volume": 1000 + i * 10,
                    "amount": close * (1000 + i * 10),
                    "pct_chg": 0.1,
                    "interval": "1m",
                }
            )
            price = close
        self.db.save_intraday_bars(pd.DataFrame(rows), code=symbol, interval="1m", data_source="test")

    def test_intraday_signal_and_paper_order_flow(self) -> None:
        signal_resp = self.client.post(
            "/api/v1/intraday/signal",
            params={"code": "AAPL", "interval": "1m", "lookback_minutes": 390, "refresh": "false"},
        )
        self.assertEqual(signal_resp.status_code, 200)
        signal_payload = signal_resp.json()
        self.assertIn(signal_payload["signal"], {"long", "neutral", "short"})
        self.assertGreater(signal_payload["vwap_session"], 0)

        account_resp = self.client.post(
            "/api/v1/paper-trading/accounts",
            json={"name": "Paper Alpha", "market": "us", "base_currency": "USD", "initial_cash": 10000},
        )
        self.assertEqual(account_resp.status_code, 200)
        account_id = account_resp.json()["id"]

        order_resp = self.client.post(
            "/api/v1/paper-trading/orders",
            json={
                "account_id": account_id,
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 2,
                "interval": "1m",
                "fill_policy": "bar_close",
                "auto_fill": True,
            },
        )
        self.assertEqual(order_resp.status_code, 200)
        order_payload = order_resp.json()
        self.assertEqual(order_payload["status"], "filled")
        self.assertIsNotNone(order_payload.get("fill"))
        self.assertIsNotNone(order_payload.get("snapshot"))

        snapshot_resp = self.client.get(f"/api/v1/paper-trading/snapshot/{account_id}")
        self.assertEqual(snapshot_resp.status_code, 200)
        snapshot_payload = snapshot_resp.json()
        self.assertEqual(snapshot_payload["account_id"], account_id)
        self.assertTrue(len(snapshot_payload["positions"]) >= 1)


if __name__ == "__main__":
    unittest.main()
