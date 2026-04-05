# -*- coding: utf-8 -*-
"""Session-mode resolution tests for multi-asset calendars."""

from datetime import date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from src.core.trading_calendar import resolve_effective_date_by_instrument, resolve_session_state


def test_perpetual_session_is_always_open() -> None:
    state = resolve_session_state(
        {"asset_class": "perpetual", "symbol": "BTCUSDT_PERP", "session_mode": "always_open_24x7"},
        current_time=datetime(2026, 4, 5, 12, 0, tzinfo=ZoneInfo("UTC")),
    )
    assert state.is_open is True
    assert state.phase == "continuous"


def test_us_equity_premarket_phase() -> None:
    with patch("src.core.trading_calendar.is_market_open", return_value=True):
        state = resolve_session_state(
            {"asset_class": "us_equity", "symbol": "AAPL", "session_mode": "us_equity_session"},
            current_time=datetime(2026, 4, 1, 8, 30, tzinfo=ZoneInfo("America/New_York")),
        )
    assert state.is_open is True
    assert state.phase == "pre_market"


def test_futures_weekend_closed_effective_date() -> None:
    state = resolve_session_state(
        {"asset_class": "future", "symbol": "ES=F", "session_mode": "futures_session"},
        current_time=datetime(2026, 4, 4, 10, 0, tzinfo=ZoneInfo("America/New_York")),  # Saturday
    )
    assert state.is_open is False
    assert state.phase == "weekend"
    assert state.effective_date == date(2026, 4, 3)  # Friday


def test_resolve_effective_date_by_instrument_uses_session_model() -> None:
    effective = resolve_effective_date_by_instrument(
        {"asset_class": "future", "symbol": "NQ=F", "session_mode": "futures_session"},
        current_time=datetime(2026, 4, 5, 8, 0, tzinfo=ZoneInfo("America/New_York")),  # Sunday pre-open
    )
    assert effective == date(2026, 4, 3)
