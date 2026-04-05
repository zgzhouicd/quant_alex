# -*- coding: utf-8 -*-
"""
Instrument input resolver.

Resolves API inputs (`stock_code`/`symbol` + optional `asset_class`) into a
canonical InstrumentSchema so downstream code can gradually migrate to
asset-aware processing while staying backward-compatible.
"""

from __future__ import annotations

import re
from typing import Optional

from src.schemas.instrument_schema import AssetClass, InstrumentSchema


_US_EQUITY_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
_US_FUTURE_YAHOO_RE = re.compile(r"^[A-Z0-9.\-]+=?F$")
_PERP_SUFFIX_RE = re.compile(r"(?:[-_/]PERP|PERP)$")
_CRYPTO_PAIR_RE = re.compile(r"^[A-Z0-9]{2,20}(?:USDT|USDC|USD|BTC|ETH)$")


def is_legacy_cn_hk_symbol(symbol: str) -> bool:
    """
    True if the string matches common A-share / HK / BSE code shapes.

    Used by API (with reject flag) and by ``main.py`` CLI to enforce the
    US equities / futures / crypto-perp product scope.
    """
    return _looks_cn_or_hk_symbol(symbol)


def _looks_cn_or_hk_symbol(symbol: str) -> bool:
    """Detect common CN/HK code shapes that this refactor intentionally excludes."""
    s = (symbol or "").strip().upper()
    if not s:
        return False
    if s.isdigit() and len(s) in (5, 6):
        return True
    if s.startswith(("SH", "SZ", "BJ")) and s[2:].isdigit():
        return True
    if s.startswith("HK") and s[2:].isdigit():
        return True
    if s.endswith((".SH", ".SZ", ".SS", ".BJ", ".HK")):
        return True
    return False


def _infer_asset_class(symbol: str) -> AssetClass:
    s = symbol.upper()
    if _PERP_SUFFIX_RE.search(s):
        return AssetClass.PERPETUAL
    if _US_FUTURE_YAHOO_RE.fullmatch(s):
        return AssetClass.FUTURE
    # Common perp symbol shape from exchange APIs can be ambiguous; here we
    # default to perpetual for crypto pairs unless explicitly overridden.
    if _CRYPTO_PAIR_RE.fullmatch(s):
        return AssetClass.PERPETUAL
    return AssetClass.US_EQUITY


def _default_session_mode(asset_class: AssetClass) -> str:
    if asset_class == AssetClass.US_EQUITY:
        return "us_equity_session"
    if asset_class == AssetClass.FUTURE:
        return "futures_session"
    return "always_open_24x7"


def _default_contract_type(asset_class: AssetClass) -> str:
    if asset_class == AssetClass.US_EQUITY:
        return "equity"
    if asset_class == AssetClass.FUTURE:
        return "future"
    return "perpetual"


def resolve_instrument_input(
    *,
    stock_code: Optional[str] = None,
    symbol: Optional[str] = None,
    asset_class: Optional[str] = None,
    exchange: Optional[str] = None,
    reject_cn_hk: bool = True,
) -> InstrumentSchema:
    """
    Resolve raw request input into a canonical instrument object.

    Priority:
    1. explicit `symbol`
    2. fallback to legacy `stock_code`
    """
    raw_symbol = (symbol or stock_code or "").strip().upper()
    if not raw_symbol:
        raise ValueError("symbol or stock_code is required")

    if reject_cn_hk and is_legacy_cn_hk_symbol(raw_symbol):
        raise ValueError(
            "CN/HK symbols are no longer accepted in this analysis path; "
            "please use US equities / futures / perpetual symbols."
        )

    if asset_class:
        try:
            resolved_asset_class = AssetClass(asset_class.strip().lower())
        except ValueError as exc:
            raise ValueError(f"unsupported asset_class: {asset_class}") from exc
    else:
        resolved_asset_class = _infer_asset_class(raw_symbol)

    if resolved_asset_class == AssetClass.US_EQUITY and not _US_EQUITY_TICKER_RE.fullmatch(raw_symbol):
        raise ValueError(f"invalid us_equity symbol format: {raw_symbol}")

    instrument = InstrumentSchema(
        asset_class=resolved_asset_class,
        symbol=raw_symbol,
        exchange=(exchange or "").strip().upper() or None,
        contract_type=_default_contract_type(resolved_asset_class),
        is_perpetual=resolved_asset_class == AssetClass.PERPETUAL,
        session_mode=_default_session_mode(resolved_asset_class),
    )
    return instrument


def instrument_to_legacy_code(instrument: InstrumentSchema) -> str:
    """
    Convert instrument to the current legacy pipeline key.

    Existing pipeline/service layers still index by `stock_code`. This helper
    allows incremental migration by carrying the canonical symbol through
    legacy entry points.
    """
    return instrument.symbol

