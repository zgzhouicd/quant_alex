"""分钟级信号与调度 API schema（路由前缀 intraday 为历史兼容）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class IntradayBarsResponse(BaseModel):
    code: str
    interval: str
    source: Optional[str] = None
    rows: int
    bars: List[Dict[str, Any]] = Field(default_factory=list)


class IntradaySignalResponse(BaseModel):
    code: str
    interval: str
    bar_start: str
    signal: str
    confidence: float
    setup: str
    invalidation: Optional[float] = None
    last_price: float
    vwap_session: float
    ema_fast: float
    ema_slow: float
    macd: float
    macd_signal: float
    rsi: float
    volume_ratio: float
    opening_range_high: float
    opening_range_low: float
    recent_high: float
    recent_low: float
    reasons: List[str] = Field(default_factory=list)
    payload: Dict[str, Any] = Field(default_factory=dict)


class IntradaySignalBatchResponse(BaseModel):
    items: List[IntradaySignalResponse] = Field(default_factory=list)


class IntradaySchedulerStartRequest(BaseModel):
    symbols: List[str] = Field(default_factory=list)
    intervals: List[str] = Field(default_factory=lambda: ["5m"])
    lookback_days: int = Field(120, ge=30, le=2000)
    lookback_minutes: int = Field(390, ge=30, le=10080)
    poll_seconds: int = Field(60, ge=5, le=86400)
    paper_account_ids: List[int] = Field(default_factory=list)
    order_quantity: float = Field(1.0, gt=0)


class IntradaySchedulerRunOnceRequest(BaseModel):
    symbols: List[str] = Field(default_factory=list)
    intervals: List[str] = Field(default_factory=lambda: ["5m"])
    lookback_days: int = Field(120, ge=30, le=2000)
    lookback_minutes: int = Field(390, ge=30, le=10080)
    paper_account_ids: List[int] = Field(default_factory=list)
    order_quantity: float = Field(1.0, gt=0)


class IntradaySchedulerStatusResponse(BaseModel):
    running: bool
    job_config: Dict[str, Any] = Field(default_factory=dict)
    last_cycle: Optional[Dict[str, Any]] = None
