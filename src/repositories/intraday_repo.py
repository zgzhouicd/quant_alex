"""分钟级数据与信号仓储。"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from src.storage import DatabaseManager, IntradaySignalRecord, StockIntradayBar

logger = logging.getLogger(__name__)


class IntradayRepository:
    """封装分钟线与信号记录的读写。"""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    def save_bars(
        self,
        df: pd.DataFrame,
        *,
        code: str,
        interval: str,
        data_source: str,
    ) -> int:
        return self.db.save_intraday_bars(df, code=code, interval=interval, data_source=data_source)

    def get_bars(
        self,
        *,
        code: str,
        interval: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[StockIntradayBar]:
        return self.db.get_intraday_bars(
            code=code,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

    def get_bars_df(
        self,
        *,
        code: str,
        interval: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> pd.DataFrame:
        bars = self.get_bars(
            code=code,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
        if not bars:
            return pd.DataFrame()
        return pd.DataFrame([bar.to_dict() for bar in bars])

    def upsert_signal(self, payload: Dict[str, Any]) -> None:
        self.db.upsert_intraday_signal(**payload)

    def get_latest_signal(self, *, code: str, interval: str) -> Optional[Dict[str, Any]]:
        row: Optional[IntradaySignalRecord] = self.db.get_latest_intraday_signal(code, interval)
        if row is None:
            return None
        return {
            "code": row.code,
            "interval": row.interval,
            "bar_start": row.bar_start.isoformat() if row.bar_start else None,
            "signal": row.signal,
            "confidence": row.confidence,
            "setup": row.setup,
            "invalidation": row.invalidation,
            "last_price": row.last_price,
            "vwap_session": row.vwap_session,
            "ema_fast": row.ema_fast,
            "ema_slow": row.ema_slow,
            "macd": row.macd,
            "macd_signal": row.macd_signal,
            "rsi": row.rsi,
            "volume_ratio": row.volume_ratio,
            "opening_range_high": row.opening_range_high,
            "opening_range_low": row.opening_range_low,
            "recent_high": row.recent_high,
            "recent_low": row.recent_low,
            "reasons": json.loads(row.reasons_json or "[]"),
            "payload": json.loads(row.payload_json or "{}"),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
