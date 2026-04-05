"""分钟级数据获取与信号编排服务。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from data_provider import DataFetcherManager
from data_provider.base import canonical_stock_code
from src.core.intraday_signal_engine import IntradaySignalEngine, IntradaySignalResult
from src.repositories.intraday_repo import IntradayRepository


class IntradaySignalService:
    """协调分钟级拉数、落库与信号计算。"""

    def __init__(
        self,
        *,
        repository: Optional[IntradayRepository] = None,
        fetcher_manager: Optional[DataFetcherManager] = None,
        engine: Optional[IntradaySignalEngine] = None,
    ):
        self.repository = repository or IntradayRepository()
        self.fetcher_manager = fetcher_manager or DataFetcherManager()
        self.engine = engine or IntradaySignalEngine()

    def fetch_and_store_bars(
        self,
        *,
        code: str,
        interval: str = "1m",
        lookback_minutes: int = 390,
    ) -> Dict[str, Any]:
        code_norm = canonical_stock_code(code)
        df, source = self.fetcher_manager.get_intraday_data(
            code_norm,
            interval=interval,
            lookback_minutes=lookback_minutes,
        )
        saved = self.repository.save_bars(
            df,
            code=code_norm,
            interval=interval,
            data_source=source,
        )
        return {
            "code": code_norm,
            "interval": interval,
            "rows": int(len(df)),
            "saved": int(saved),
            "source": source,
        }

    def analyze_symbol(
        self,
        *,
        code: str,
        interval: str = "1m",
        lookback_minutes: int = 390,
        refresh_data: bool = True,
    ) -> Dict[str, Any]:
        code_norm = canonical_stock_code(code)
        if refresh_data:
            self.fetch_and_store_bars(
                code=code_norm,
                interval=interval,
                lookback_minutes=lookback_minutes,
            )

        start_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=lookback_minutes)
        df = self.repository.get_bars_df(
            code=code_norm,
            interval=interval,
            start_time=start_time,
        )
        if df.empty:
            fallback_limit = max(30, int(lookback_minutes / max(self._interval_to_minutes(interval), 1)))
            df = self.repository.get_bars_df(
                code=code_norm,
                interval=interval,
                limit=fallback_limit,
            )
        result = self.engine.analyze(df, code=code_norm, interval=interval)
        self.repository.upsert_signal(result.to_record_payload())
        return result.to_api_dict()

    def analyze_symbols(
        self,
        *,
        symbols: List[str],
        interval: str = "1m",
        lookback_minutes: int = 390,
        refresh_data: bool = True,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for symbol in symbols:
            if not (symbol or "").strip():
                continue
            results.append(
                self.analyze_symbol(
                    code=symbol,
                    interval=interval,
                    lookback_minutes=lookback_minutes,
                    refresh_data=refresh_data,
                )
            )
        return results

    def get_latest_signal(self, *, code: str, interval: str = "1m") -> Optional[Dict[str, Any]]:
        return self.repository.get_latest_signal(code=canonical_stock_code(code), interval=interval)

    @staticmethod
    def _interval_to_minutes(interval: str) -> int:
        text = (interval or "1m").strip().lower()
        if text.endswith("m") and text[:-1].isdigit():
            return max(1, int(text[:-1]))
        if text.endswith("h") and text[:-1].isdigit():
            return max(1, int(text[:-1]) * 60)
        return 1
