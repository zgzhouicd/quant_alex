# -*- coding: utf-8 -*-
"""
多资产分析用的统一标的模型（InstrumentSchema）。

本模块提供一等公民的 instrument 定义，使系统能从「仅股票代码」输入
过渡到「按资产类别-aware」的输入。
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
    """API / 服务层共用的规范化标的表示。"""

    asset_class: AssetClass = Field(..., description="资产类别")
    symbol: str = Field(..., description="标的代码 / 符号")
    exchange: Optional[str] = Field(None, description="交易所 / 交易场所")
    quote_currency: Optional[str] = Field(None, description="计价货币")
    contract_type: Optional[str] = Field(None, description="合约类型：equity / future / perpetual")
    underlying: Optional[str] = Field(None, description="标的资产符号（期货等）")
    expiry: Optional[str] = Field(None, description="合约到期（如适用）")
    is_perpetual: bool = Field(False, description="是否为永续合约")
    session_mode: Optional[str] = Field(
        None,
        description="会话模式：us_equity_session / futures_session / always_open_24x7",
    )

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: str) -> str:
        symbol = (value or "").strip().upper()
        if not symbol:
            raise ValueError("symbol cannot be empty")
        return symbol

