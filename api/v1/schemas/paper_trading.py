"""Paper trading API schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PaperTradingAccountCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    market: str = Field("us", min_length=2, max_length=16)
    base_currency: str = Field("USD", min_length=3, max_length=8)
    initial_cash: float = Field(100000.0, gt=0)


class PaperTradingAccountItem(BaseModel):
    id: int
    name: str
    market: str
    base_currency: str
    initial_cash: float
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PaperTradingAccountListResponse(BaseModel):
    accounts: List[PaperTradingAccountItem] = Field(default_factory=list)


class PaperTradingOrderCreateRequest(BaseModel):
    account_id: int
    symbol: str = Field(..., min_length=1, max_length=16)
    side: str = Field(..., pattern="^(buy|sell)$")
    quantity: float = Field(..., gt=0)
    interval: str = Field("1m", min_length=2, max_length=8)
    requested_price: Optional[float] = Field(None, gt=0)
    signal_bar_start: Optional[str] = None
    fill_policy: str = Field("bar_close", min_length=4, max_length=32)
    note: Optional[str] = Field(None, max_length=255)
    auto_fill: bool = True


class PaperTradingOrderItem(BaseModel):
    id: int
    account_id: int
    symbol: str
    interval: str
    side: str
    quantity: float
    order_type: str
    requested_price: Optional[float] = None
    signal_bar_start: Optional[str] = None
    fill_policy: str
    status: str
    note: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PaperTradingFillItem(BaseModel):
    id: int
    order_id: int
    account_id: int
    symbol: str
    interval: str
    side: str
    quantity: float
    fill_price: float
    fee: float
    fill_timestamp: Optional[str] = None
    bar_start: Optional[str] = None
    created_at: Optional[str] = None


class PaperTradingOrderListResponse(BaseModel):
    items: List[PaperTradingOrderItem] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


class PaperTradingFillListResponse(BaseModel):
    items: List[PaperTradingFillItem] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


class PaperTradingSnapshotResponse(BaseModel):
    id: int
    account_id: int
    snapshot_time: Optional[str] = None
    cash_balance: float
    market_value: float
    total_equity: float
    realized_pnl: float
    unrealized_pnl: float
    positions: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[str] = None


class PaperTradingOrderExecutionResponse(BaseModel):
    id: int
    account_id: int
    symbol: str
    interval: str
    side: str
    quantity: float
    order_type: str
    requested_price: Optional[float] = None
    signal_bar_start: Optional[str] = None
    fill_policy: str
    status: str
    note: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    fill: Optional[PaperTradingFillItem] = None
    snapshot: Optional[PaperTradingSnapshotResponse] = None
