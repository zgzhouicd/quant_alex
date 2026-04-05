# -*- coding: utf-8 -*-
"""Contract tests for get_derivatives_snapshot tool."""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agent.tools.data_tools import _handle_get_derivatives_snapshot


class _DummyInstrument:
    def model_dump(self):
        return {
            "symbol": "BTCUSDT_PERP",
            "asset_class": "perpetual",
            "exchange": "BINANCE",
            "session_mode": "always_open_24x7",
        }


class TestGetDerivativesSnapshotTool(unittest.TestCase):
    def test_returns_router_snapshot_payload(self) -> None:
        router_instance = MagicMock()
        router_instance.get_derivatives_snapshot.return_value = SimpleNamespace(
            capability="derivatives_snapshot",
            success=True,
            degraded=False,
            provider="binance_futures_public",
            error=None,
            data={"status": "ok", "provider_symbol": "BTCUSDT"},
        )

        with patch("src.agent.tools.data_tools._get_fetcher_manager", return_value=object()), \
             patch("src.services.instrument_resolver.resolve_instrument_input", return_value=_DummyInstrument()), \
             patch("src.services.capability_router.MarketCapabilityRouter", return_value=router_instance):
            result = _handle_get_derivatives_snapshot("BTCUSDT_PERP", asset_class="perpetual")

        self.assertTrue(result["success"])
        self.assertEqual(result["provider"], "binance_futures_public")
        self.assertEqual(result["snapshot"]["provider_symbol"], "BTCUSDT")
        self.assertEqual(result["instrument"]["asset_class"], "perpetual")

    def test_rejects_invalid_asset_class(self) -> None:
        result = _handle_get_derivatives_snapshot("BTCUSDT_PERP", asset_class="us_equity")
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
