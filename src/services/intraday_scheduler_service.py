"""日线级信号调度服务。"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.services.intraday_signal_service import IntradaySignalService
from src.services.paper_trading_service import PaperTradingService


class IntradaySchedulerService:
    """以后台线程低频执行日线信号与模拟交易。"""

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
        lookback_days: int = 120,
        lookback_minutes: Optional[int] = None,
        poll_seconds: int = 3600,
        paper_account_ids: Optional[List[int]] = None,
        order_quantity: float = 1.0,
    ) -> Dict[str, Any]:
        days = self._resolve_lookback_days(lookback_days, lookback_minutes)
        with self._lock:
            self._job_config = {
                "symbols": [s for s in symbols if (s or "").strip()],
                "intervals": [i for i in intervals if (i or "").strip()],
                "lookback_days": days,
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
        lookback_days: int = 120,
        lookback_minutes: Optional[int] = None,
        paper_account_ids: Optional[List[int]] = None,
        order_quantity: float = 1.0,
    ) -> Dict[str, Any]:
        days = self._resolve_lookback_days(lookback_days, lookback_minutes)
        config = {
            "symbols": [s for s in symbols if (s or "").strip()],
            "intervals": [i for i in intervals if (i or "").strip()],
            "lookback_days": days,
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
            self._stop_event.wait(timeout=max(5, int(config.get("poll_seconds", 60))))

    def _execute_cycle(self, config: Dict[str, Any]) -> Dict[str, Any]:
        started_at = datetime.utcnow().isoformat() + "Z"
        results: List[Dict[str, Any]] = []
        for interval in config.get("intervals", []):
            for symbol in config.get("symbols", []):
                signal = self.signal_service.analyze_symbol(
                    code=symbol,
                    interval=interval,
                    lookback_days=int(config.get("lookback_days", 120)),
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

    @staticmethod
    def _resolve_lookback_days(lookback_days: int, lookback_minutes: Optional[int]) -> int:
        if lookback_minutes is not None:
            return max(30, min(2000, int(lookback_minutes / 1440) or 1))
        return max(30, min(2000, int(lookback_days or 120)))


_SCHEDULER_SINGLETON: Optional[IntradaySchedulerService] = None


def get_intraday_scheduler_service() -> IntradaySchedulerService:
    global _SCHEDULER_SINGLETON
    if _SCHEDULER_SINGLETON is None:
        _SCHEDULER_SINGLETON = IntradaySchedulerService()
    return _SCHEDULER_SINGLETON
