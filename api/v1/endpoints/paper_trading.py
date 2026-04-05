"""Paper trading API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.paper_trading import (
    PaperTradingAccountCreateRequest,
    PaperTradingAccountItem,
    PaperTradingAccountListResponse,
    PaperTradingFillItem,
    PaperTradingFillListResponse,
    PaperTradingOrderCreateRequest,
    PaperTradingOrderExecutionResponse,
    PaperTradingOrderItem,
    PaperTradingOrderListResponse,
    PaperTradingSnapshotResponse,
)
from src.services.paper_trading_service import PaperTradingService

router = APIRouter()


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail={"error": "validation_error", "message": str(exc)})


@router.post(
    "/accounts",
    response_model=PaperTradingAccountItem,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Create paper trading account",
)
def create_paper_account(request: PaperTradingAccountCreateRequest) -> PaperTradingAccountItem:
    service = PaperTradingService()
    try:
        return PaperTradingAccountItem(**service.create_account(**request.model_dump()))
    except ValueError as exc:
        raise _bad_request(exc)


@router.get(
    "/accounts",
    response_model=PaperTradingAccountListResponse,
    summary="List paper trading accounts",
)
def list_paper_accounts(
    include_inactive: bool = Query(False),
) -> PaperTradingAccountListResponse:
    service = PaperTradingService()
    return PaperTradingAccountListResponse(
        accounts=[PaperTradingAccountItem(**item) for item in service.list_accounts(include_inactive=include_inactive)]
    )


@router.post(
    "/orders",
    response_model=PaperTradingOrderExecutionResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Submit paper trading order",
)
def create_paper_order(request: PaperTradingOrderCreateRequest) -> PaperTradingOrderExecutionResponse:
    service = PaperTradingService()
    try:
        data = service.submit_order(
            account_id=request.account_id,
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            interval=request.interval,
            requested_price=request.requested_price,
            signal_bar_start=service._coerce_datetime(request.signal_bar_start),
            fill_policy=request.fill_policy,
            note=request.note,
            auto_fill=request.auto_fill,
        )
        return PaperTradingOrderExecutionResponse(**data)
    except ValueError as exc:
        raise _bad_request(exc)


@router.get(
    "/orders",
    response_model=PaperTradingOrderListResponse,
    summary="List paper trading orders",
)
def list_paper_orders(
    account_id: int | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> PaperTradingOrderListResponse:
    service = PaperTradingService()
    data = service.list_orders(account_id=account_id, status=status, page=page, page_size=page_size)
    return PaperTradingOrderListResponse(
        items=[PaperTradingOrderItem(**item) for item in data["items"]],
        total=data["total"],
        page=data["page"],
        page_size=data["page_size"],
    )


@router.get(
    "/fills",
    response_model=PaperTradingFillListResponse,
    summary="List paper trading fills",
)
def list_paper_fills(
    account_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> PaperTradingFillListResponse:
    service = PaperTradingService()
    data = service.list_fills(account_id=account_id, page=page, page_size=page_size)
    return PaperTradingFillListResponse(
        items=[PaperTradingFillItem(**item) for item in data["items"]],
        total=data["total"],
        page=data["page"],
        page_size=data["page_size"],
    )


@router.get(
    "/snapshot/{account_id}",
    response_model=PaperTradingSnapshotResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Get latest paper trading account snapshot",
)
def get_paper_snapshot(account_id: int) -> PaperTradingSnapshotResponse:
    service = PaperTradingService()
    try:
        return PaperTradingSnapshotResponse(**service.get_account_snapshot(account_id=account_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(exc)})
