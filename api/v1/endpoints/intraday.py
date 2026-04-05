"""分钟级数据与信号 API。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, HTTPException, Query

from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.intraday import (
    IntradayBarsResponse,
    IntradaySchedulerRunOnceRequest,
    IntradaySchedulerStartRequest,
    IntradaySchedulerStatusResponse,
    IntradaySignalBatchResponse,
    IntradaySignalResponse,
)
from src.repositories.intraday_repo import IntradayRepository
from src.services.intraday_scheduler_service import get_intraday_scheduler_service
from src.services.intraday_signal_service import IntradaySignalService

router = APIRouter()


def _bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=400, detail={"error": "validation_error", "message": message})


@router.get(
    "/bars",
    response_model=IntradayBarsResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Query intraday bars",
)
def get_intraday_bars(
    code: str = Query(..., min_length=1),
    interval: str = Query("1m"),
    lookback_minutes: int = Query(390, ge=30, le=10080),
    refresh: bool = Query(True),
) -> IntradayBarsResponse:
    service = IntradaySignalService()
    repo = IntradayRepository()
    if refresh:
        fetch_result = service.fetch_and_store_bars(code=code, interval=interval, lookback_minutes=lookback_minutes)
        source = fetch_result["source"]
    else:
        source = None
    start_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=lookback_minutes)
    bars = repo.get_bars(code=code.upper(), interval=interval, start_time=start_time)
    payload = []
    for row in bars:
        item = row.to_dict()
        item["bar_start"] = row.bar_start.isoformat() if row.bar_start else None
        item["session_date"] = row.session_date.isoformat() if row.session_date else None
        payload.append(item)
    return IntradayBarsResponse(code=code.upper(), interval=interval, source=source, rows=len(payload), bars=payload)


@router.post(
    "/signal",
    response_model=IntradaySignalResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Generate intraday signal for one symbol",
)
def analyze_intraday_signal(
    code: str = Query(..., min_length=1),
    interval: str = Query("1m"),
    lookback_minutes: int = Query(390, ge=30, le=10080),
    refresh: bool = Query(True),
) -> IntradaySignalResponse:
    service = IntradaySignalService()
    result = service.analyze_symbol(
        code=code,
        interval=interval,
        lookback_minutes=lookback_minutes,
        refresh_data=refresh,
    )
    return IntradaySignalResponse(**result)


@router.post(
    "/signals/batch",
    response_model=IntradaySignalBatchResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Generate intraday signals for multiple symbols",
)
def analyze_intraday_signal_batch(
    symbols: List[str],
    interval: str = Query("1m"),
    lookback_minutes: int = Query(390, ge=30, le=10080),
    refresh: bool = Query(True),
) -> IntradaySignalBatchResponse:
    if not symbols:
        raise _bad_request("symbols is required")
    service = IntradaySignalService()
    items = service.analyze_symbols(
        symbols=symbols,
        interval=interval,
        lookback_minutes=lookback_minutes,
        refresh_data=refresh,
    )
    return IntradaySignalBatchResponse(items=[IntradaySignalResponse(**item) for item in items])


@router.get(
    "/signal/latest",
    response_model=IntradaySignalResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Get latest stored intraday signal",
)
def get_latest_intraday_signal(
    code: str = Query(..., min_length=1),
    interval: str = Query("1m"),
) -> IntradaySignalResponse:
    service = IntradaySignalService()
    result = service.get_latest_signal(code=code, interval=interval)
    if result is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "signal not found"})
    return IntradaySignalResponse(**result)


@router.post(
    "/scheduler/start",
    response_model=IntradaySchedulerStatusResponse,
    responses={400: {"model": ErrorResponse}},
    summary="Start background intraday scheduler",
)
def start_intraday_scheduler(request: IntradaySchedulerStartRequest) -> IntradaySchedulerStatusResponse:
    if not request.symbols:
        raise _bad_request("symbols is required")
    scheduler = get_intraday_scheduler_service()
    return IntradaySchedulerStatusResponse(**scheduler.start(**request.model_dump()))


@router.post(
    "/scheduler/run-once",
    response_model=IntradaySchedulerStatusResponse,
    responses={400: {"model": ErrorResponse}},
    summary="Run intraday scheduler cycle once",
)
def run_intraday_scheduler_once(request: IntradaySchedulerRunOnceRequest) -> IntradaySchedulerStatusResponse:
    if not request.symbols:
        raise _bad_request("symbols is required")
    scheduler = get_intraday_scheduler_service()
    result = scheduler.run_once(**request.model_dump())
    return IntradaySchedulerStatusResponse(running=False, job_config={}, last_cycle=result)


@router.post(
    "/scheduler/stop",
    response_model=IntradaySchedulerStatusResponse,
    summary="Stop background intraday scheduler",
)
def stop_intraday_scheduler() -> IntradaySchedulerStatusResponse:
    scheduler = get_intraday_scheduler_service()
    return IntradaySchedulerStatusResponse(**scheduler.stop())


@router.get(
    "/scheduler/status",
    response_model=IntradaySchedulerStatusResponse,
    summary="Get intraday scheduler status",
)
def get_intraday_scheduler_status() -> IntradaySchedulerStatusResponse:
    scheduler = get_intraday_scheduler_service()
    return IntradaySchedulerStatusResponse(**scheduler.status())
