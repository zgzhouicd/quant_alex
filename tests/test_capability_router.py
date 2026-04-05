# -*- coding: utf-8 -*-
"""Unit tests for capability-first market router."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import patch

from src.services.capability_router import MarketCapabilityRouter


@dataclass
class _Quote:
    symbol: str


class _StubFetcherManager:
    def __init__(self):
        self.quote_calls = []

    def get_realtime_quote(self, stock_code: str, *, log_final_failure: bool = True):
        self.quote_calls.append(stock_code)
        if stock_code == "BTCUSDT":
            return _Quote(symbol=stock_code)
        return None

    def get_daily_data(self, stock_code: str, start_date=None, end_date=None, days: int = 30):
        return [{"code": stock_code}], "stub_provider"

    def get_stock_name(self, stock_code: str, allow_realtime: bool = True):
        return f"NAME_{stock_code}"

    def get_fundamental_context(self, stock_code: str, budget_seconds: float = 1.5):
        return {"status": "ok", "symbol": stock_code}

    def build_failed_fundamental_context(self, stock_code: str, reason: str):
        return {"status": "failed", "symbol": stock_code, "reason": reason}


def test_derivatives_perp_realtime_candidate_fallback() -> None:
    router = MarketCapabilityRouter(fetcher_manager=_StubFetcherManager())
    result = router.get_realtime_quote(
        {
            "asset_class": "perpetual",
            "symbol": "BTCUSDT_PERP",
            "session_mode": "always_open_24x7",
        }
    )
    assert result.success is True
    assert getattr(result.data, "symbol", "") == "BTCUSDT"


def test_fundamentals_not_supported_for_perpetual() -> None:
    router = MarketCapabilityRouter(fetcher_manager=_StubFetcherManager())
    result = router.get_fundamental_context(
        {
            "asset_class": "perpetual",
            "symbol": "BTCUSDT_PERP",
            "session_mode": "always_open_24x7",
        }
    )
    assert result.success is False
    assert result.degraded is True
    assert isinstance(result.data, dict)
    assert result.data.get("status") == "not_supported"


def test_instrument_meta_for_future_uses_symbol_display_name() -> None:
    router = MarketCapabilityRouter(fetcher_manager=_StubFetcherManager())
    result = router.get_instrument_meta(
        {
            "asset_class": "future",
            "symbol": "ES=F",
            "session_mode": "futures_session",
        }
    )
    assert result.success is True
    assert result.data["display_name"] == "ES=F"


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_derivatives_snapshot_binance_public_path() -> None:
    router = MarketCapabilityRouter(fetcher_manager=_StubFetcherManager())

    def _mock_get(url, params=None, timeout=None):
        path = str(url)
        if path.endswith("/fapi/v1/premiumIndex"):
            return _FakeResponse(
                {
                    "markPrice": "50000",
                    "indexPrice": "49950",
                    "lastFundingRate": "0.0012",
                    "nextFundingTime": 1760000000000,
                    "time": 1759999999000,
                }
            )
        if path.endswith("/fapi/v1/fundingRate"):
            return _FakeResponse(
                [
                    {"fundingRate": "0.0012"},
                    {"fundingRate": "0.0010"},
                    {"fundingRate": "0.0008"},
                ]
            )
        if path.endswith("/fapi/v1/openInterest"):
            return _FakeResponse({"openInterest": "12345", "time": 1760000000000})
        if path.endswith("/futures/data/openInterestHist"):
            return _FakeResponse(
                [
                    {"sumOpenInterest": "10000", "sumOpenInterestValue": "500000000", "timestamp": 1760000000000},
                    {"sumOpenInterest": "10600", "sumOpenInterestValue": "530000000", "timestamp": 1760000300000},
                ]
            )
        if path.endswith("/futures/data/globalLongShortAccountRatio"):
            return _FakeResponse(
                [
                    {"longShortRatio": "1.95", "longAccount": "0.66", "shortAccount": "0.34", "timestamp": 1760000300000}
                ]
            )
        if path.endswith("/futures/data/takerlongshortRatio"):
            return _FakeResponse([{"buySellRatio": "1.8", "timestamp": 1760000300000}])
        raise AssertionError(f"unexpected request path: {path}")

    with patch("src.services.capability_router.requests.get", side_effect=_mock_get):
        result = router.get_derivatives_snapshot(
            {
                "asset_class": "perpetual",
                "symbol": "BTCUSDT_PERP",
                "session_mode": "always_open_24x7",
            }
        )

    assert result.success is True
    assert result.provider == "binance_futures_public"
    assert result.data["provider_symbol"] == "BTCUSDT"
    assert result.data["status"] in {"ok", "partial"}
    assert result.data["funding_rate"]["last_rate"] == 0.0012
    assert result.data["open_interest"]["current_contracts"] == 12345.0
    assert isinstance(result.data.get("risk_flags"), list)
    assert result.data["risk_flags"]


def test_derivatives_snapshot_not_supported_for_cme_style_symbol() -> None:
    router = MarketCapabilityRouter(fetcher_manager=_StubFetcherManager())
    result = router.get_derivatives_snapshot(
        {
            "asset_class": "future",
            "symbol": "ES=F",
            "session_mode": "futures_session",
        }
    )
    assert result.success is False
    assert result.degraded is True
    assert result.data["status"] == "not_supported"
