"""分钟级信号滚动调度（可选联动 paper trading）。"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.intraday_defaults import (
    DEFAULT_DAILY_LOOKBACK_DAYS,
    DEFAULT_INTRADAY_INTERVAL,
    DEFAULT_LOOKBACK_MINUTES,
    DEFAULT_POLL_SECONDS,
)
from src.services.intraday_signal_service import IntradaySignalService
from src.services.paper_trading_service import PaperTradingService


class IntradaySchedulerService:
    """后台线程按 poll_seconds 滚动：拉分钟线 → 算信号 → 可选 paper 撮合。"""

    def __init__(
        self,
        *,
        signal_service: Optional[IntradaySignalService] = None,
        paper_service: Optional[PaperTradingService] = None,
    ):
        self.signal_service = signal_service or IntradaySignalService()
        self.paper_service = paper_service or PaperTradingService()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        self._job_config: Dict[str, Any] = {}
        self._last_cycle: Optional[Dict[str, Any]] = None

    def start(
        self,
        *,
        symbols: List[str],
        intervals: List[str],
        lookback_days: int = DEFAULT_DAILY_LOOKBACK_DAYS,
        lookback_minutes: int = DEFAULT_LOOKBACK_MINUTES,
        poll_seconds: int = DEFAULT_POLL_SECONDS,
        paper_account_ids: Optional[List[int]] = None,
        order_quantity: float = 1.0,
    ) -> Dict[str, Any]:
        with self._lock:
            self._job_config = {
                "symbols": [s for s in symbols if (s or "").strip()],
                "intervals": [i for i in intervals if (i or "").strip()] or [DEFAULT_INTRADAY_INTERVAL],
                "lookback_days": max(30, min(2000, int(lookback_days))),
                "lookback_minutes": max(30, min(10080, int(lookback_minutes))),
                "poll_seconds": max(5, int(poll_seconds)),
                "paper_account_ids": paper_account_ids or [],
                "order_quantity": float(order_quantity),
            }
            if self._thread is not None and self._thread.is_alive():
                return self.status()
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True, name="intraday-scheduler")
            self._thread.start()
            return self.status()

    def stop(self) -> Dict[str, Any]:
        self._stop_event.set()
        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join(timeout=2.0)
        return self.status()

    def run_once(
        self,
        *,
        symbols: List[str],
        intervals: List[str],
        lookback_days: int = DEFAULT_DAILY_LOOKBACK_DAYS,
        lookback_minutes: int = DEFAULT_LOOKBACK_MINUTES,
        paper_account_ids: Optional[List[int]] = None,
        order_quantity: float = 1.0,
    ) -> Dict[str, Any]:
        config = {
            "symbols": [s for s in symbols if (s or "").strip()],
            "intervals": [i for i in intervals if (i or "").strip()] or [DEFAULT_INTRADAY_INTERVAL],
            "lookback_days": max(30, min(2000, int(lookback_days))),
            "lookback_minutes": max(30, min(10080, int(lookback_minutes))),
            "paper_account_ids": paper_account_ids or [],
            "order_quantity": float(order_quantity),
        }
        self._last_cycle = self._execute_cycle(config)
        return self._last_cycle

    def status(self) -> Dict[str, Any]:
        with self._lock:
            running = self._thread is not None and self._thread.is_alive()
            return {
                "running": running,
                "job_config": dict(self._job_config),
                "last_cycle": self._last_cycle,
            }

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                config = dict(self._job_config)
            self._last_cycle = self._execute_cycle(config)
            self._stop_event.wait(timeout=max(5, int(config.get("poll_seconds", DEFAULT_POLL_SECONDS))))

    def _execute_cycle(self, config: Dict[str, Any]) -> Dict[str, Any]:
        started_at = datetime.utcnow().isoformat() + "Z"
        results: List[Dict[str, Any]] = []
        lookback_minutes = int(config.get("lookback_minutes", DEFAULT_LOOKBACK_MINUTES))
        lookback_days = int(config.get("lookback_days", DEFAULT_DAILY_LOOKBACK_DAYS))
        for interval in config.get("intervals", [DEFAULT_INTRADAY_INTERVAL]):
            for symbol in config.get("symbols", []):
                signal = self.signal_service.analyze_symbol(
                    code=symbol,
                    interval=interval,
                    lookback_days=lookback_days,
                    lookback_minutes=lookback_minutes,
                    refresh_data=True,
                )
                results.append(signal)
                for account_id in config.get("paper_account_ids", []):
                    self.paper_service.apply_signal(
                        account_id=account_id,
                        signal_payload=signal,
                        quantity=float(config.get("order_quantity", 1.0)),
                    )
        return {
            "started_at": started_at,
            "finished_at": datetime.utcnow().isoformat() + "Z",
            "signal_count": len(results),
            "results": results,
        }


_SCHEDULER_SINGLETON: Optional[IntradaySchedulerService] = None


def get_intraday_scheduler_service() -> IntradaySchedulerService:
    global _SCHEDULER_SINGLETON
    if _SCHEDULER_SINGLETON is None:
        _SCHEDULER_SINGLETON = IntradaySchedulerService()
    return _SCHEDULER_SINGLETON
