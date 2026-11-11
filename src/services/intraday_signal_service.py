"""分钟级 K 线拉取、落库与结构化信号编排服务。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from data_provider import DataFetcherManager
from data_provider.base import canonical_stock_code
from src.core.intraday_defaults import DEFAULT_INTRADAY_INTERVAL, DEFAULT_LOOKBACK_MINUTES
from src.core.intraday_signal_engine import IntradaySignalEngine, IntradaySignalResult
from src.repositories.intraday_repo import IntradayRepository


class IntradaySignalService:
    """协调分钟线拉数、落库与信号计算。"""

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
        interval: str = DEFAULT_INTRADAY_INTERVAL,
        lookback_days: int = 120,
        lookback_minutes: Optional[int] = None,
    ) -> Dict[str, Any]:
        code_norm = canonical_stock_code(code)
        interval_norm = self._normalize_interval(interval)
        days = self._resolve_lookback_days(lookback_days, lookback_minutes)
        if interval_norm == "1d":
            daily_df, source = self.fetcher_manager.get_daily_data(code_norm, days=days)
            df = self._daily_to_bar_frame(daily_df, interval=interval_norm)
        else:
            df, source = self.fetcher_manager.get_intraday_data(
                code_norm,
                interval=interval_norm,
                lookback_minutes=lookback_minutes or days * 1440,
            )
        saved = self.repository.save_bars(
            df,
            code=code_norm,
            interval=interval_norm,
            data_source=source,
        )
        return {
            "code": code_norm,
            "interval": interval_norm,
            "rows": int(len(df)),
            "saved": int(saved),
            "source": source,
        }

    def analyze_symbol(
        self,
        *,
        code: str,
        interval: str = DEFAULT_INTRADAY_INTERVAL,
        lookback_days: int = 120,
        lookback_minutes: Optional[int] = DEFAULT_LOOKBACK_MINUTES,
        refresh_data: bool = True,
    ) -> Dict[str, Any]:
        code_norm = canonical_stock_code(code)
        interval_norm = self._normalize_interval(interval)
        days = self._resolve_lookback_days(lookback_days, lookback_minutes)
        if refresh_data:
            self.fetch_and_store_bars(
                code=code_norm,
                interval=interval_norm,
                lookback_days=days,
                lookback_minutes=lookback_minutes,
            )

        start_delta = timedelta(days=days) if interval_norm == "1d" else timedelta(minutes=lookback_minutes or days * 1440)
        start_time = datetime.now(timezone.utc).replace(tzinfo=None) - start_delta
        df = self.repository.get_bars_df(
            code=code_norm,
            interval=interval_norm,
            start_time=start_time,
        )
        if df.empty:
            fallback_limit = days if interval_norm == "1d" else int((lookback_minutes or days * 1440) / max(self._interval_to_minutes(interval_norm), 1))
            fallback_limit = max(30, fallback_limit)
            df = self.repository.get_bars_df(
                code=code_norm,
                interval=interval_norm,
                limit=fallback_limit,
            )
        result = self.engine.analyze(df, code=code_norm, interval=interval_norm)
        self.repository.upsert_signal(result.to_record_payload())
        return result.to_api_dict()

    def analyze_symbols(
        self,
        *,
        symbols: List[str],
        interval: str = DEFAULT_INTRADAY_INTERVAL,
        lookback_days: int = 120,
        lookback_minutes: Optional[int] = DEFAULT_LOOKBACK_MINUTES,
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
                    lookback_days=lookback_days,
                    lookback_minutes=lookback_minutes,
                    refresh_data=refresh_data,
                )
            )
        return results

    def get_latest_signal(self, *, code: str, interval: str = DEFAULT_INTRADAY_INTERVAL) -> Optional[Dict[str, Any]]:
        return self.repository.get_latest_signal(
            code=canonical_stock_code(code),
            interval=self._normalize_interval(interval),
        )

    @staticmethod
    def _daily_to_bar_frame(df, *, interval: str):
        frame = df.copy()
        if "timestamp" not in frame.columns:
            frame["timestamp"] = frame.get("date")
        frame["timestamp"] = frame["timestamp"].apply(lambda value: value.to_pydatetime() if hasattr(value, "to_pydatetime") else value)
        frame["interval"] = interval
        keep_cols = ["timestamp", "open", "high", "low", "close", "volume", "amount", "pct_chg", "interval"]
        return frame[[col for col in keep_cols if col in frame.columns]].copy()

    @staticmethod
    def _normalize_interval(interval: str) -> str:
        text = (interval or DEFAULT_INTRADAY_INTERVAL).strip().lower()
        if text in {"d", "day", "daily", "1day"}:
            return "1d"
        return text

    @staticmethod
    def _resolve_lookback_days(lookback_days: int, lookback_minutes: Optional[int]) -> int:
        if lookback_minutes is not None:
            return max(1, min(2000, int(lookback_minutes / 1440) or 1))
        return max(30, min(2000, int(lookback_days or 120)))

    @staticmethod
    def _interval_to_minutes(interval: str) -> int:
        text = (interval or DEFAULT_INTRADAY_INTERVAL).strip().lower()
        if text.endswith("d") and text[:-1].isdigit():
            return max(1, int(text[:-1]) * 1440)
        if text.endswith("m") and text[:-1].isdigit():
            return max(1, int(text[:-1]))
        if text.endswith("h") and text[:-1].isdigit():
            return max(1, int(text[:-1]) * 60)
        return 1
