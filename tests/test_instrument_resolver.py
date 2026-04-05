# -*- coding: utf-8 -*-
"""Unit tests for instrument input resolution."""

import pytest

from src.services.instrument_resolver import resolve_instrument_input


def test_resolve_us_equity_symbol() -> None:
    inst = resolve_instrument_input(symbol="AAPL")
    assert inst.asset_class.value == "us_equity"
    assert inst.symbol == "AAPL"
    assert inst.contract_type == "equity"
    assert inst.session_mode == "us_equity_session"


def test_resolve_future_symbol() -> None:
    inst = resolve_instrument_input(symbol="ES=F")
    assert inst.asset_class.value == "future"
    assert inst.contract_type == "future"
    assert inst.session_mode == "futures_session"


def test_resolve_perpetual_symbol() -> None:
    inst = resolve_instrument_input(symbol="BTCUSDT_PERP")
    assert inst.asset_class.value == "perpetual"
    assert inst.contract_type == "perpetual"
    assert inst.is_perpetual is True
    assert inst.session_mode == "always_open_24x7"


def test_reject_cn_hk_symbols_by_default() -> None:
    with pytest.raises(ValueError, match="CN/HK symbols"):
        resolve_instrument_input(stock_code="600519")

    with pytest.raises(ValueError, match="CN/HK symbols"):
        resolve_instrument_input(stock_code="00700.HK")


def test_allow_explicit_asset_class() -> None:
    inst = resolve_instrument_input(symbol="NQ=F", asset_class="future", exchange="CME")
    assert inst.asset_class.value == "future"
    assert inst.exchange == "CME"
