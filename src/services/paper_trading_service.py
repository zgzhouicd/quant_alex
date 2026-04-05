"""分钟级模拟交易服务。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, func, select

from data_provider.base import canonical_stock_code
from src.storage import (
    DatabaseManager,
    PaperTradingAccount,
    PaperTradingFill,
    PaperTradingOrder,
    PortfolioIntradaySnapshot,
    StockIntradayBar,
)


VALID_ORDER_SIDES = {"buy", "sell"}
VALID_ORDER_STATUS = {"pending", "filled", "cancelled", "rejected"}


class PaperTradingService:
    """负责 paper account、订单、成交与分钟权益快照。"""

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager.get_instance()

    def create_account(
        self,
        *,
        name: str,
        market: str = "us",
        base_currency: str = "USD",
        initial_cash: float = 100000.0,
    ) -> Dict[str, Any]:
        if not (name or "").strip():
            raise ValueError("name is required")
        if initial_cash <= 0:
            raise ValueError("initial_cash must be > 0")
        with self.db.get_session() as session:
            row = PaperTradingAccount(
                name=name.strip(),
                market=(market or "us").strip().lower(),
                base_currency=(base_currency or "USD").strip().upper(),
                initial_cash=float(initial_cash),
                is_active=True,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._account_to_dict(row)

    def list_accounts(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        with self.db.get_session() as session:
            query = select(PaperTradingAccount)
            if not include_inactive:
                query = query.where(PaperTradingAccount.is_active.is_(True))
            rows = session.execute(query.order_by(PaperTradingAccount.id.asc())).scalars().all()
            return [self._account_to_dict(row) for row in rows]

    def submit_order(
        self,
        *,
        account_id: int,
        symbol: str,
        side: str,
        quantity: float,
        interval: str = "1m",
        requested_price: Optional[float] = None,
        signal_bar_start: Optional[datetime] = None,
        fill_policy: str = "bar_close",
        note: Optional[str] = None,
        auto_fill: bool = True,
    ) -> Dict[str, Any]:
        side_norm = (side or "").strip().lower()
        if side_norm not in VALID_ORDER_SIDES:
            raise ValueError("side must be buy or sell")
        if quantity <= 0:
            raise ValueError("quantity must be > 0")

        with self.db.get_session() as session:
            account = session.get(PaperTradingAccount, account_id)
            if account is None or not account.is_active:
                raise ValueError(f"paper account not found: {account_id}")

            row = PaperTradingOrder(
                account_id=account_id,
                symbol=canonical_stock_code(symbol),
                interval=(interval or "1m").strip().lower(),
                side=side_norm,
                quantity=float(quantity),
                requested_price=requested_price,
                signal_bar_start=signal_bar_start,
                fill_policy=(fill_policy or "bar_close").strip().lower(),
                status="pending",
                note=(note or "").strip() or None,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            order_dict = self._order_to_dict(row)

        if auto_fill:
            return self.execute_order(order_id=order_dict["id"])
        return order_dict

    def execute_order(self, *, order_id: int, fee: float = 0.0) -> Dict[str, Any]:
        with self.db.get_session() as session:
            order = session.get(PaperTradingOrder, order_id)
            if order is None:
                raise ValueError(f"paper order not found: {order_id}")
            if order.status != "pending":
                return self._order_to_dict(order)

            fill_context = self._resolve_fill_context(session=session, order=order)
            fill = PaperTradingFill(
                order_id=order.id,
                account_id=order.account_id,
                symbol=order.symbol,
                interval=order.interval,
                side=order.side,
                quantity=order.quantity,
                fill_price=fill_context["fill_price"],
                fee=float(fee),
                fill_timestamp=fill_context["fill_timestamp"],
                bar_start=fill_context["bar_start"],
            )
            session.add(fill)
            order.status = "filled"
            order.updated_at = datetime.now()
            session.flush()
            snapshot = self._rebuild_account_snapshot(session=session, account_id=order.account_id)
            session.commit()
            return {
                **self._order_to_dict(order),
                "fill": self._fill_to_dict(fill),
                "snapshot": snapshot,
            }

    def apply_signal(
        self,
        *,
        account_id: int,
        signal_payload: Dict[str, Any],
        quantity: float = 1.0,
    ) -> Optional[Dict[str, Any]]:
        signal = str(signal_payload.get("signal") or "neutral").strip().lower()
        symbol = canonical_stock_code(str(signal_payload.get("code") or ""))
        if not symbol or quantity <= 0:
            return None

        snapshot = self.get_account_snapshot(account_id=account_id)
        current_position = next((p for p in snapshot["positions"] if p["symbol"] == symbol), None)
        current_qty = float(current_position["quantity"]) if current_position else 0.0

        side: Optional[str] = None
        order_qty: float = float(quantity)
        if signal == "long":
            if current_qty > 0:
                return None
            side = "buy"
            if current_qty < 0:
                order_qty = abs(current_qty) + quantity
        elif signal == "short":
            if current_qty < 0:
                return None
            side = "sell"
            if current_qty > 0:
                order_qty = current_qty + quantity
        elif signal == "neutral" and current_qty != 0:
            side = "sell" if current_qty > 0 else "buy"
            order_qty = abs(current_qty)
        else:
            return None

        bar_start = self._coerce_datetime(signal_payload.get("bar_start"))
        requested_price = self._coerce_float(signal_payload.get("last_price"))
        return self.submit_order(
            account_id=account_id,
            symbol=symbol,
            side=side,
            quantity=order_qty,
            interval=str(signal_payload.get("interval") or "1m"),
            requested_price=requested_price,
            signal_bar_start=bar_start,
            fill_policy="bar_close",
            note=f"auto_signal:{signal}",
            auto_fill=True,
        )

    def list_orders(
        self,
        *,
        account_id: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        with self.db.get_session() as session:
            query = select(PaperTradingOrder)
            if account_id is not None:
                query = query.where(PaperTradingOrder.account_id == account_id)
            if status:
                query = query.where(PaperTradingOrder.status == status)
            count_query = select(func.count()).select_from(query.order_by(None).subquery())
            total = int(session.execute(count_query).scalar_one() or 0)
            rows = session.execute(
                query.order_by(desc(PaperTradingOrder.created_at))
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars().all()
            return {
                "items": [self._order_to_dict(row) for row in rows],
                "total": total,
                "page": page,
                "page_size": page_size,
            }

    def list_fills(
        self,
        *,
        account_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        with self.db.get_session() as session:
            query = select(PaperTradingFill)
            if account_id is not None:
                query = query.where(PaperTradingFill.account_id == account_id)
            count_query = select(func.count()).select_from(query.order_by(None).subquery())
            total = int(session.execute(count_query).scalar_one() or 0)
            rows = session.execute(
                query.order_by(desc(PaperTradingFill.fill_timestamp))
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars().all()
            return {
                "items": [self._fill_to_dict(row) for row in rows],
                "total": total,
                "page": page,
                "page_size": page_size,
            }

    def get_account_snapshot(self, *, account_id: int) -> Dict[str, Any]:
        with self.db.get_session() as session:
            account = session.get(PaperTradingAccount, account_id)
            if account is None:
                raise ValueError(f"paper account not found: {account_id}")
            latest = session.execute(
                select(PortfolioIntradaySnapshot)
                .where(PortfolioIntradaySnapshot.account_id == account_id)
                .order_by(desc(PortfolioIntradaySnapshot.snapshot_time))
                .limit(1)
            ).scalar_one_or_none()
            if latest is None:
                snapshot = self._rebuild_account_snapshot(session=session, account_id=account_id)
                session.commit()
                return snapshot
            return self._snapshot_to_dict(latest)

    def _resolve_fill_context(self, *, session: Any, order: PaperTradingOrder) -> Dict[str, Any]:
        bar = None
        if order.signal_bar_start is not None:
            bar = session.execute(
                select(StockIntradayBar).where(
                    StockIntradayBar.code == order.symbol,
                    StockIntradayBar.interval == order.interval,
                    StockIntradayBar.bar_start == order.signal_bar_start,
                ).limit(1)
            ).scalar_one_or_none()
        if bar is None:
            bar = session.execute(
                select(StockIntradayBar)
                .where(
                    StockIntradayBar.code == order.symbol,
                    StockIntradayBar.interval == order.interval,
                )
                .order_by(desc(StockIntradayBar.bar_start))
                .limit(1)
            ).scalar_one_or_none()
        if bar is None:
            raise ValueError(f"no intraday bar available for {order.symbol}/{order.interval}")

        if order.fill_policy == "next_bar_open":
            next_bar = session.execute(
                select(StockIntradayBar)
                .where(
                    StockIntradayBar.code == order.symbol,
                    StockIntradayBar.interval == order.interval,
                    StockIntradayBar.bar_start > bar.bar_start,
                )
                .order_by(StockIntradayBar.bar_start.asc())
                .limit(1)
            ).scalar_one_or_none()
            if next_bar is not None:
                bar = next_bar
                fill_price = float(next_bar.open)
            else:
                fill_price = float(bar.close)
        else:
            fill_price = float(order.requested_price or bar.close)
        return {
            "fill_price": fill_price,
            "fill_timestamp": bar.bar_start,
            "bar_start": bar.bar_start,
        }

    def _rebuild_account_snapshot(self, *, session: Any, account_id: int) -> Dict[str, Any]:
        account = session.get(PaperTradingAccount, account_id)
        if account is None:
            raise ValueError(f"paper account not found: {account_id}")
        fills = session.execute(
            select(PaperTradingFill)
            .where(PaperTradingFill.account_id == account_id)
            .order_by(PaperTradingFill.fill_timestamp.asc(), PaperTradingFill.id.asc())
        ).scalars().all()

        cash = float(account.initial_cash)
        realized_pnl = 0.0
        positions: Dict[str, Dict[str, Any]] = {}

        for fill in fills:
            symbol = fill.symbol
            state = positions.setdefault(symbol, {"quantity": 0.0, "avg_price": 0.0, "last_price": fill.fill_price})
            qty = float(state["quantity"])
            avg_price = float(state["avg_price"])
            fill_qty = float(fill.quantity)
            price = float(fill.fill_price)
            signed_fill = fill_qty if fill.side == "buy" else -fill_qty

            cash += -fill_qty * price - float(fill.fee) if fill.side == "buy" else fill_qty * price - float(fill.fee)

            if qty == 0 or (qty > 0 and signed_fill > 0) or (qty < 0 and signed_fill < 0):
                total_qty = qty + signed_fill
                total_abs = abs(qty) + abs(signed_fill)
                avg_price = (
                    ((abs(qty) * avg_price) + (abs(signed_fill) * price)) / total_abs
                    if total_abs > 0 else 0.0
                )
                qty = total_qty
            else:
                closing_qty = min(abs(qty), abs(signed_fill))
                if qty > 0:
                    realized_pnl += closing_qty * (price - avg_price)
                else:
                    realized_pnl += closing_qty * (avg_price - price)
                qty += signed_fill
                if qty == 0:
                    avg_price = 0.0
                elif (qty > 0 and signed_fill > 0) or (qty < 0 and signed_fill < 0):
                    avg_price = price
            state["quantity"] = qty
            state["avg_price"] = avg_price
            state["last_price"] = price

        positions_payload: List[Dict[str, Any]] = []
        market_value = 0.0
        unrealized_pnl = 0.0
        latest_snapshot_time = datetime.now()

        for symbol, state in positions.items():
            qty = float(state["quantity"])
            if abs(qty) < 1e-8:
                continue
            last_bar = session.execute(
                select(StockIntradayBar)
                .where(StockIntradayBar.code == symbol)
                .order_by(desc(StockIntradayBar.bar_start))
                .limit(1)
            ).scalar_one_or_none()
            last_price = float(last_bar.close) if last_bar is not None and last_bar.close is not None else float(state["last_price"])
            latest_snapshot_time = max(latest_snapshot_time, last_bar.bar_start) if last_bar is not None else latest_snapshot_time
            exposure = qty * last_price
            pnl = (last_price - state["avg_price"]) * qty if qty >= 0 else (state["avg_price"] - last_price) * abs(qty)
            market_value += exposure
            unrealized_pnl += pnl
            positions_payload.append(
                {
                    "symbol": symbol,
                    "quantity": qty,
                    "avg_price": round(float(state["avg_price"]), 6),
                    "last_price": round(last_price, 6),
                    "market_value": round(exposure, 6),
                    "unrealized_pnl": round(pnl, 6),
                }
            )

        total_equity = cash + market_value
        snapshot = session.execute(
            select(PortfolioIntradaySnapshot).where(
                PortfolioIntradaySnapshot.account_id == account_id,
                PortfolioIntradaySnapshot.snapshot_time == latest_snapshot_time,
            ).limit(1)
        ).scalar_one_or_none()
        if snapshot is None:
            snapshot = PortfolioIntradaySnapshot(
                account_id=account_id,
                snapshot_time=latest_snapshot_time,
            )
            session.add(snapshot)
        snapshot.cash_balance = cash
        snapshot.market_value = market_value
        snapshot.total_equity = total_equity
        snapshot.realized_pnl = realized_pnl
        snapshot.unrealized_pnl = unrealized_pnl
        snapshot.positions_json = json.dumps(positions_payload, ensure_ascii=False)
        session.flush()
        return self._snapshot_to_dict(snapshot)

    @staticmethod
    def _coerce_datetime(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.replace(tzinfo=None) if value.tzinfo is not None else value
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)

    @staticmethod
    def _coerce_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _account_to_dict(row: PaperTradingAccount) -> Dict[str, Any]:
        return {
            "id": row.id,
            "name": row.name,
            "market": row.market,
            "base_currency": row.base_currency,
            "initial_cash": row.initial_cash,
            "is_active": row.is_active,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    @staticmethod
    def _order_to_dict(row: PaperTradingOrder) -> Dict[str, Any]:
        return {
            "id": row.id,
            "account_id": row.account_id,
            "symbol": row.symbol,
            "interval": row.interval,
            "side": row.side,
            "quantity": row.quantity,
            "order_type": row.order_type,
            "requested_price": row.requested_price,
            "signal_bar_start": row.signal_bar_start.isoformat() if row.signal_bar_start else None,
            "fill_policy": row.fill_policy,
            "status": row.status,
            "note": row.note,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    @staticmethod
    def _fill_to_dict(row: PaperTradingFill) -> Dict[str, Any]:
        return {
            "id": row.id,
            "order_id": row.order_id,
            "account_id": row.account_id,
            "symbol": row.symbol,
            "interval": row.interval,
            "side": row.side,
            "quantity": row.quantity,
            "fill_price": row.fill_price,
            "fee": row.fee,
            "fill_timestamp": row.fill_timestamp.isoformat() if row.fill_timestamp else None,
            "bar_start": row.bar_start.isoformat() if row.bar_start else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    @staticmethod
    def _snapshot_to_dict(row: PortfolioIntradaySnapshot) -> Dict[str, Any]:
        return {
            "id": row.id,
            "account_id": row.account_id,
            "snapshot_time": row.snapshot_time.isoformat() if row.snapshot_time else None,
            "cash_balance": row.cash_balance,
            "market_value": row.market_value,
            "total_equity": row.total_equity,
            "realized_pnl": row.realized_pnl,
            "unrealized_pnl": row.unrealized_pnl,
            "positions": json.loads(row.positions_json or "[]"),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
