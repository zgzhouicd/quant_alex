# -*- coding: utf-8 -*-
"""Offline smoke tests for major /api/v1 routes (and /api/health).

Uses temp DB + ADMIN_AUTH_ENABLED=false. Avoids network via mocks where needed.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
from fastapi.testclient import TestClient

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from api.app import create_app
from data_provider.base import DataFetchError
from src.config import Config
from src.storage import DatabaseManager


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


class ApiV1SmokeMatrixTestCase(unittest.TestCase):
    """Broad HTTP smoke matrix for v1 API."""

    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.db_path = self.data_dir / "api_v1_smoke.db"
        self.env_path.write_text(
            "\n".join(
                [
                    "STOCK_LIST=AAPL",
                    "GEMINI_API_KEY=test",
                    "ADMIN_AUTH_ENABLED=false",
                    f"DATABASE_PATH={self.db_path}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.db_path)
        Config.reset_instance()
        DatabaseManager.reset_instance()
        app = create_app(static_dir=self.data_dir / "empty-static")
        self.client = TestClient(app)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def test_root_health_ok(self) -> None:
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body.get("status"), "ok")
        self.assertIn("timestamp", body)

    def test_v1_health_ok(self) -> None:
        r = self.client.get("/api/v1/health")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body.get("status"), "ok")

    def test_auth_status_ok(self) -> None:
        r = self.client.get("/api/v1/auth/status")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("authEnabled", data)
        self.assertIsInstance(data["authEnabled"], bool)

    def test_agent_skills_ok(self) -> None:
        r = self.client.get("/api/v1/agent/skills")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("skills", data)

    def test_history_list_ok(self) -> None:
        r = self.client.get("/api/v1/history", params={"page": 1, "limit": 5})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("items", data)

    def test_backtest_results_ok(self) -> None:
        r = self.client.get("/api/v1/backtest/results", params={"page": 1, "limit": 5})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("items", data)

    def test_backtest_performance_no_summary_404(self) -> None:
        # Fresh DB has no backtest_summaries row; endpoint should 404 predictably.
        r = self.client.get("/api/v1/backtest/performance")
        self.assertEqual(r.status_code, 404)
        body = r.json()
        # http_exception_handler flattens ErrorResponse-shaped detail to top-level JSON.
        self.assertEqual(body.get("error"), "not_found")

    def test_usage_summary_ok(self) -> None:
        r = self.client.get("/api/v1/usage/summary", params={"period": "month"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("period", data)

    def test_stocks_parse_import_json_ok(self) -> None:
        r = self.client.post("/api/v1/stocks/parse-import", json={"text": "AAPL"})
        self.assertEqual(r.status_code, 200, msg=r.text)

    def test_system_config_schema_ok(self) -> None:
        r = self.client.get("/api/v1/system/config/schema")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(isinstance(data, dict))

    def test_portfolio_prefix_not_found(self) -> None:
        r = self.client.get("/api/v1/portfolio/accounts")
        self.assertEqual(r.status_code, 404)

    def test_analysis_empty_codes_400(self) -> None:
        r = self.client.post("/api/v1/analysis/analyze", json={"async_mode": False})
        self.assertEqual(r.status_code, 400)
        detail = r.json()
        self.assertEqual(detail.get("error"), "validation_error")

    def test_intraday_signal_minute_mock_fetch_defaults_5m_200(self) -> None:
        """默认省略 interval 时走 5m，并通过 mock 分钟拉数完成闭环。"""
        rows = []
        base = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
        price = 100.0
        for i in range(50):
            ts = base + timedelta(minutes=i * 5)
            close = price + 0.05
            rows.append(
                {
                    "timestamp": ts,
                    "open": price,
                    "high": close + 0.02,
                    "low": price - 0.02,
                    "close": close,
                    "volume": 10_000 + i * 100,
                    "amount": close * (10_000 + i * 100),
                    "pct_chg": 0.05,
                    "interval": "5m",
                }
            )
            price = close
        intraday_df = pd.DataFrame(rows)
        with patch(
            "src.services.intraday_signal_service.DataFetcherManager.get_intraday_data",
            return_value=(intraday_df, "mock-intraday"),
        ):
            r = self.client.post(
                "/api/v1/intraday/signal",
                params={"code": "AAPL", "lookback_minutes": 390, "refresh": "true"},
            )
        self.assertEqual(r.status_code, 200, msg=r.text)
        data = r.json()
        self.assertEqual(data.get("code"), "AAPL")
        self.assertEqual(data.get("interval"), "5m")
        self.assertIn(data.get("signal"), {"long", "short", "neutral"})
        self.assertEqual(data.get("payload", {}).get("signal_timeframe"), "intraday")

    def test_intraday_signal_data_fetch_error_502(self) -> None:
        with patch(
            "data_provider.DataFetcherManager.get_intraday_data",
            side_effect=DataFetchError("mock upstream failure"),
        ):
            r = self.client.post(
                "/api/v1/intraday/signal",
                params={
                    "code": "AAPL",
                    "interval": "1m",
                    "lookback_minutes": 120,
                    "refresh": "true",
                },
            )
        self.assertEqual(r.status_code, 502)
        detail = r.json()
        self.assertEqual(detail.get("error"), "data_fetch_error")
        self.assertIn("mock upstream failure", detail.get("message", ""))

    def test_intraday_signal_refresh_false_with_seed_200(self) -> None:
        db = DatabaseManager.get_instance()
        base = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
        rows = []
        price = 100.0
        for i in range(45):
            close = price + 0.2
            rows.append(
                {
                    "timestamp": base + timedelta(minutes=i),
                    "open": price,
                    "high": close + 0.1,
                    "low": price - 0.1,
                    "close": close,
                    "volume": 1000 + i,
                    "amount": close * (1000 + i),
                    "pct_chg": 0.1,
                    "interval": "1m",
                }
            )
            price = close
        db.save_intraday_bars(pd.DataFrame(rows), code="AAPL", interval="1m", data_source="test")

        r = self.client.post(
            "/api/v1/intraday/signal",
            params={
                "code": "AAPL",
                "interval": "1m",
                "lookback_minutes": 390,
                "refresh": "false",
            },
        )
        self.assertEqual(r.status_code, 200, msg=r.text)
        data = r.json()
        self.assertIn(data.get("signal"), {"long", "short", "neutral"})

    def test_agent_models_ok(self) -> None:
        r = self.client.get("/api/v1/agent/models")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("models", data)
        self.assertIsInstance(data["models"], list)


if __name__ == "__main__":
    unittest.main()
