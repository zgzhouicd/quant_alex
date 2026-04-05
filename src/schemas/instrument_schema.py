# -*- coding: utf-8 -*-
"""
Unified instrument schema for multi-asset analysis.

This module introduces a first-class instrument model so the system can
move from "stock-code-only" inputs to asset-aware inputs.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class AssetClass(str, Enum):
    US_EQUITY = "us_equity"
    FUTURE = "future"
    PERPETUAL = "perpetual"


class InstrumentSchema(BaseModel):
    """Canonical instrument representation used by API/services."""

    asset_class: AssetClass = Field(..., description="Asset class")
    symbol: str = Field(..., description="Instrument symbol")
    exchange: Optional[str] = Field(None, description="Exchange / venue")
    quote_currency: Optional[str] = Field(None, description="Quote currency")
    contract_type: Optional[str] = Field(None, description="equity/future/perpetual")
    underlying: Optional[str] = Field(None, description="Underlying asset symbol")
    expiry: Optional[str] = Field(None, description="Contract expiry (if applicable)")
    is_perpetual: bool = Field(False, description="Whether this is a perpetual contract")
    session_mode: Optional[str] = Field(
        None,
        description="Session mode: us_equity_session/futures_session/always_open_24x7",
    )

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: str) -> str:
        symbol = (value or "").strip().upper()
        if not symbol:
            raise ValueError("symbol cannot be empty")
        return symbol

