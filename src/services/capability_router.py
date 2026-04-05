# -*- coding: utf-8 -*-
"""
===================================
多资产能力路由器
===================================

职责：
1. 以“能力(capability)”而非“单一股票数据源”进行路由
2. 根据 instrument 的 asset_class 选择适配路径
3. 对未支持能力返回结构化降级结果（不抛异常中断主流程）
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from data_provider.base import DataFetcherManager
from src.services.instrument_resolver import instrument_to_legacy_code

logger = logging.getLogger(__name__)

_DERIVATIVES_TIMEOUT_SECONDS = 3.5
_BINANCE_FAPI_BASE_URL = "https://fapi.binance.com"
_BINANCE_QUOTE_SUFFIXES = ("USDT", "USDC", "BUSD", "USD")


@dataclass
class RoutedCapabilityResult:
    """Standard capability routing result payload."""

    capability: str
    success: bool
    data: Any = None
    provider: Optional[str] = None
    error: Optional[str] = None
    degraded: bool = False


class MarketCapabilityRouter:
    """
    Capability-first market data router.

    当前实现策略（P0）：
    - 复用 DataFetcherManager 作为底层执行器
    - 在路由层区分 asset_class 与 capability
    - 对 derivatives 扩展能力提供公共数据快照（fail-open）
    """

    def __init__(self, fetcher_manager: Optional[DataFetcherManager] = None):
        self.fetcher_manager = fetcher_manager or DataFetcherManager()

    @staticmethod
    def _asset_class(instrument: Optional[Dict[str, Any]]) -> str:
        value = (instrument or {}).get("asset_class")
        return str(value or "us_equity").strip().lower()

    @staticmethod
    def _symbol(instrument: Optional[Dict[str, Any]]) -> str:
        if not instrument:
            return ""
        try:
            return instrument_to_legacy_code(instrument)  # type: ignore[arg-type]
        except Exception:
            return str(instrument.get("symbol") or "").strip().upper()

    @staticmethod
    def _symbol_candidates(instrument: Optional[Dict[str, Any]]) -> list[str]:
        """
        Build candidate symbols for provider fallback.

        For perpetual contracts we try stripping common PERP suffixes as a
        best-effort fallback when providers do not recognize the perpetual tag.
        """
        symbol = MarketCapabilityRouter._symbol(instrument)
        if not symbol:
            return []

        candidates = [symbol]
        upper = symbol.upper()
        for suffix in ("_PERP", "-PERP", "/PERP", "PERP"):
            if upper.endswith(suffix):
                stripped = upper[: -len(suffix)].strip("-_/")
                if stripped and stripped not in candidates:
                    candidates.append(stripped)
        return candidates

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _utc_iso_from_ms(value: Any) -> Optional[str]:
        try:
            if value is None:
                return None
            millis = int(value)
            return datetime.fromtimestamp(millis / 1000.0, tz=timezone.utc).isoformat()
        except (TypeError, ValueError, OSError):
            return None

    @staticmethod
    def _http_get_json(url: str, *, params: Dict[str, Any]) -> Any:
        response = requests.get(url, params=params, timeout=_DERIVATIVES_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and "msg" in payload and "code" in payload:
            try:
                code_num = int(payload.get("code"))
            except (TypeError, ValueError):
                code_num = -1
            if code_num != 0:
                raise RuntimeError(f"provider returned code={payload.get('code')}, msg={payload.get('msg')}")
        return payload

    @classmethod
    def _normalize_binance_symbol(cls, instrument: Dict[str, Any]) -> str:
        for candidate in cls._symbol_candidates(instrument):
            normalized = str(candidate or "").strip().upper()
            if not normalized:
                continue
            for token in ("/", "-", "_"):
                normalized = normalized.replace(token, "")
            if normalized.endswith("PERP"):
                normalized = normalized[:-4]
            if not normalized or not normalized.isalnum():
                continue
            for quote in _BINANCE_QUOTE_SUFFIXES:
                if normalized.endswith(quote) and len(normalized) > len(quote) + 1:
                    return normalized
        return ""

    def get_historical_bars(
        self,
        instrument: Dict[str, Any],
        *,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 30,
    ) -> RoutedCapabilityResult:
        """Route `historical_bars` capability."""
        asset_class = self._asset_class(instrument)
        capability = "historical_bars"

        if asset_class not in {"us_equity", "future", "perpetual"}:
            return RoutedCapabilityResult(
                capability=capability,
                success=False,
                error=f"unsupported asset_class for {capability}: {asset_class}",
                degraded=True,
            )

        last_error: Optional[str] = None
        for candidate in self._symbol_candidates(instrument):
            try:
                df, provider = self.fetcher_manager.get_daily_data(
                    candidate,
                    start_date=start_date,
                    end_date=end_date,
                    days=days,
                )
                return RoutedCapabilityResult(
                    capability=capability,
                    success=True,
                    data=df,
                    provider=provider,
                )
            except Exception as exc:
                last_error = str(exc)
                logger.debug(
                    "[CapabilityRouter] historical_bars failed: symbol=%s asset_class=%s err=%s",
                    candidate,
                    asset_class,
                    exc,
                )

        return RoutedCapabilityResult(
            capability=capability,
            success=False,
            error=last_error or "all providers failed for historical_bars",
            degraded=True,
        )

    def get_realtime_quote(self, instrument: Dict[str, Any]) -> RoutedCapabilityResult:
        """Route `realtime_quote` capability."""
        asset_class = self._asset_class(instrument)
        capability = "realtime_quote"

        if asset_class not in {"us_equity", "future", "perpetual"}:
            return RoutedCapabilityResult(
                capability=capability,
                success=False,
                error=f"unsupported asset_class for {capability}: {asset_class}",
                degraded=True,
            )

        last_error: Optional[str] = None
        for candidate in self._symbol_candidates(instrument):
            try:
                quote = self.fetcher_manager.get_realtime_quote(candidate, log_final_failure=False)
                if quote is not None:
                    return RoutedCapabilityResult(
                        capability=capability,
                        success=True,
                        data=quote,
                    )
            except Exception as exc:
                last_error = str(exc)
                logger.debug(
                    "[CapabilityRouter] realtime_quote failed: symbol=%s asset_class=%s err=%s",
                    candidate,
                    asset_class,
                    exc,
                )

        return RoutedCapabilityResult(
            capability=capability,
            success=False,
            error=last_error or "all providers failed for realtime_quote",
            degraded=True,
        )

    def get_instrument_meta(self, instrument: Dict[str, Any]) -> RoutedCapabilityResult:
        """Route `instrument_meta` capability."""
        capability = "instrument_meta"
        symbol = self._symbol(instrument)
        asset_class = self._asset_class(instrument)
        if not symbol:
            return RoutedCapabilityResult(
                capability=capability,
                success=False,
                error="empty symbol",
                degraded=True,
            )

        # Non-equity instruments default to symbol display name.
        if asset_class in {"future", "perpetual"}:
            return RoutedCapabilityResult(
                capability=capability,
                success=True,
                data={"symbol": symbol, "display_name": symbol},
                provider="instrument_router",
            )

        try:
            display_name = self.fetcher_manager.get_stock_name(symbol, allow_realtime=False) or symbol
            return RoutedCapabilityResult(
                capability=capability,
                success=True,
                data={"symbol": symbol, "display_name": display_name},
                provider="DataFetcherManager",
            )
        except Exception as exc:
            return RoutedCapabilityResult(
                capability=capability,
                success=False,
                data={"symbol": symbol, "display_name": symbol},
                error=str(exc),
                degraded=True,
            )

    def get_fundamental_context(
        self,
        instrument: Dict[str, Any],
        *,
        budget_seconds: float = 1.5,
    ) -> RoutedCapabilityResult:
        """Route `fundamentals` capability."""
        capability = "fundamentals"
        symbol = self._symbol(instrument)
        asset_class = self._asset_class(instrument)
        if not symbol:
            return RoutedCapabilityResult(
                capability=capability,
                success=False,
                error="empty symbol",
                degraded=True,
            )

        if asset_class != "us_equity":
            payload = {
                "market": "global",
                "status": "not_supported",
                "reason": f"fundamentals not supported for asset_class={asset_class}",
                "coverage": {},
                "source_chain": [],
            }
            return RoutedCapabilityResult(
                capability=capability,
                success=False,
                data=payload,
                degraded=True,
            )

        try:
            payload = self.fetcher_manager.get_fundamental_context(
                symbol,
                budget_seconds=budget_seconds,
            )
            return RoutedCapabilityResult(
                capability=capability,
                success=True,
                data=payload,
                provider="DataFetcherManager",
            )
        except Exception as exc:
            try:
                payload = self.fetcher_manager.build_failed_fundamental_context(symbol, str(exc))
            except Exception:
                payload = {
                    "market": "us",
                    "status": "failed",
                    "reason": str(exc),
                    "coverage": {},
                    "source_chain": [],
                }
            return RoutedCapabilityResult(
                capability=capability,
                success=False,
                data=payload,
                error=str(exc),
                degraded=True,
            )

    def get_derivatives_snapshot(self, instrument: Dict[str, Any]) -> RoutedCapabilityResult:
        """
        Route derivatives-only capability bundle.

        当前接入 Binance 公共合约接口（无需鉴权）：
        - premiumIndex: mark/index/funding
        - fundingRate: 最近 funding 历史
        - openInterest + openInterestHist
        - globalLongShortAccountRatio + takerlongshortRatio（作为清算压力代理）

        说明：
        - 对不可获取字段返回结构化降级（fail-open）
        - delivery futures / 传统期货暂不支持，返回 not_supported
        """
        capability = "derivatives_snapshot"
        asset_class = self._asset_class(instrument)
        if asset_class not in {"future", "perpetual"}:
            payload = {
                "status": "not_supported",
                "reason": f"derivatives snapshot not supported for asset_class={asset_class}",
                "funding_rate": None,
                "open_interest": None,
                "liquidation_data": None,
                "basis_data": None,
                "term_structure": None,
                "risk_flags": [],
                "errors": [],
            }
            return RoutedCapabilityResult(
                capability=capability,
                success=False,
                data=payload,
                degraded=True,
            )

        symbol = self._symbol(instrument)
        provider_symbol = self._normalize_binance_symbol(instrument)
        if not provider_symbol:
            payload = {
                "status": "not_supported",
                "reason": (
                    "no compatible public derivatives provider for symbol; "
                    "currently only Binance-style crypto contracts are supported"
                ),
                "symbol": symbol,
                "provider_symbol": None,
                "funding_rate": None,
                "open_interest": None,
                "liquidation_data": None,
                "basis_data": None,
                "term_structure": None,
                "risk_flags": [],
                "errors": [],
            }
            return RoutedCapabilityResult(
                capability=capability,
                success=False,
                data=payload,
                degraded=True,
            )

        payload: Dict[str, Any] = {
            "status": "partial",
            "asset_class": asset_class,
            "symbol": symbol,
            "provider_symbol": provider_symbol,
            "exchange": "BINANCE",
            "provider": "binance_futures_public",
            "snapshot_time": datetime.now(timezone.utc).isoformat(),
            "funding_rate": None,
            "open_interest": None,
            "liquidation_data": None,
            "basis_data": None,
            "term_structure": {
                "status": "not_supported",
                "reason": "term structure for delivery futures not available in this snapshot",
            },
            "risk_flags": [],
            "errors": [],
        }

        # 1) premium index -> basis + latest funding
        try:
            premium = self._http_get_json(
                f"{_BINANCE_FAPI_BASE_URL}/fapi/v1/premiumIndex",
                params={"symbol": provider_symbol},
            )
            if isinstance(premium, dict):
                mark_price = self._safe_float(premium.get("markPrice"))
                index_price = self._safe_float(premium.get("indexPrice"))
                last_funding_rate = self._safe_float(premium.get("lastFundingRate"))
                basis_abs = None
                basis_bps = None
                if mark_price is not None and index_price not in (None, 0):
                    basis_abs = mark_price - index_price
                    basis_bps = (basis_abs / index_price) * 10000.0

                payload["basis_data"] = {
                    "mark_price": mark_price,
                    "index_price": index_price,
                    "basis_abs": basis_abs,
                    "basis_bps": basis_bps,
                    "time": self._utc_iso_from_ms(premium.get("time")),
                }
                payload["funding_rate"] = {
                    "last_rate": last_funding_rate,
                    "next_funding_time": self._utc_iso_from_ms(premium.get("nextFundingTime")),
                    "annualized_estimate_pct": (
                        round(last_funding_rate * 3 * 365 * 100, 2)
                        if last_funding_rate is not None
                        else None
                    ),
                }
        except Exception as exc:
            payload["errors"].append(f"premium_index_failed: {exc}")
            logger.debug("[CapabilityRouter] derivatives premium index failed: %s", exc)

        # 2) funding history
        try:
            funding_hist = self._http_get_json(
                f"{_BINANCE_FAPI_BASE_URL}/fapi/v1/fundingRate",
                params={"symbol": provider_symbol, "limit": 3},
            )
            if isinstance(funding_hist, list):
                rates = [
                    self._safe_float(item.get("fundingRate"))
                    for item in funding_hist
                    if isinstance(item, dict)
                ]
                rates = [item for item in rates if item is not None]
                if rates:
                    if not isinstance(payload.get("funding_rate"), dict):
                        payload["funding_rate"] = {}
                    payload["funding_rate"]["recent_rates"] = rates
                    payload["funding_rate"]["avg_recent_rate"] = sum(rates) / len(rates)
        except Exception as exc:
            payload["errors"].append(f"funding_history_failed: {exc}")
            logger.debug("[CapabilityRouter] derivatives funding history failed: %s", exc)

        # 3) open interest current + short-window change
        try:
            oi_current = self._http_get_json(
                f"{_BINANCE_FAPI_BASE_URL}/fapi/v1/openInterest",
                params={"symbol": provider_symbol},
            )
            block = {
                "current_contracts": (
                    self._safe_float(oi_current.get("openInterest"))
                    if isinstance(oi_current, dict)
                    else None
                ),
                "time": (
                    self._utc_iso_from_ms(oi_current.get("time"))
                    if isinstance(oi_current, dict)
                    else None
                ),
            }

            oi_hist = self._http_get_json(
                f"{_BINANCE_FAPI_BASE_URL}/futures/data/openInterestHist",
                params={"symbol": provider_symbol, "period": "5m", "limit": 2},
            )
            if isinstance(oi_hist, list) and len(oi_hist) >= 2:
                prev = oi_hist[-2] if isinstance(oi_hist[-2], dict) else {}
                latest = oi_hist[-1] if isinstance(oi_hist[-1], dict) else {}
                prev_val = self._safe_float(prev.get("sumOpenInterest"))
                latest_val = self._safe_float(latest.get("sumOpenInterest"))
                latest_notional = self._safe_float(latest.get("sumOpenInterestValue"))
                if prev_val not in (None, 0) and latest_val is not None:
                    block["oi_change_5m_pct"] = ((latest_val - prev_val) / prev_val) * 100.0
                block["hist_latest_contracts"] = latest_val
                block["hist_latest_notional"] = latest_notional
                block["hist_latest_time"] = self._utc_iso_from_ms(latest.get("timestamp"))

            payload["open_interest"] = block
        except Exception as exc:
            payload["errors"].append(f"open_interest_failed: {exc}")
            logger.debug("[CapabilityRouter] derivatives open interest failed: %s", exc)

        # 4) liquidation pressure proxy (public endpoint has no direct liquidation map)
        try:
            ls_hist = self._http_get_json(
                f"{_BINANCE_FAPI_BASE_URL}/futures/data/globalLongShortAccountRatio",
                params={"symbol": provider_symbol, "period": "5m", "limit": 2},
            )
            taker_hist = self._http_get_json(
                f"{_BINANCE_FAPI_BASE_URL}/futures/data/takerlongshortRatio",
                params={"symbol": provider_symbol, "period": "5m", "limit": 2},
            )

            latest_ls = {}
            if isinstance(ls_hist, list) and ls_hist:
                latest_ls = ls_hist[-1] if isinstance(ls_hist[-1], dict) else {}

            latest_taker = {}
            if isinstance(taker_hist, list) and taker_hist:
                latest_taker = taker_hist[-1] if isinstance(taker_hist[-1], dict) else {}

            payload["liquidation_data"] = {
                "status": "proxy",
                "method": "positioning_pressure_proxy",
                "long_short_ratio": self._safe_float(latest_ls.get("longShortRatio")),
                "long_account_pct": self._safe_float(latest_ls.get("longAccount")),
                "short_account_pct": self._safe_float(latest_ls.get("shortAccount")),
                "taker_buy_sell_ratio": self._safe_float(latest_taker.get("buySellRatio")),
                "time": self._utc_iso_from_ms(
                    latest_ls.get("timestamp") or latest_taker.get("timestamp")
                ),
                "note": (
                    "No direct public liquidation heatmap endpoint; "
                    "using long/short and taker imbalance as pressure proxy"
                ),
            }
        except Exception as exc:
            payload["errors"].append(f"liquidation_proxy_failed: {exc}")
            logger.debug("[CapabilityRouter] derivatives liquidation proxy failed: %s", exc)

        # 5) risk flags + leverage posture
        risk_flags: list[Dict[str, Any]] = []
        funding_rate = self._safe_float((payload.get("funding_rate") or {}).get("last_rate"))
        if funding_rate is not None:
            if abs(funding_rate) >= 0.001:
                risk_flags.append(
                    {
                        "category": "funding_extreme",
                        "severity": "high",
                        "value": funding_rate,
                        "description": "Funding rate is extreme; leverage squeeze risk elevated.",
                    }
                )
            elif abs(funding_rate) >= 0.0005:
                risk_flags.append(
                    {
                        "category": "funding_stretched",
                        "severity": "medium",
                        "value": funding_rate,
                        "description": "Funding rate is stretched; avoid aggressive leverage.",
                    }
                )

        basis_bps = self._safe_float((payload.get("basis_data") or {}).get("basis_bps"))
        if basis_bps is not None:
            if abs(basis_bps) >= 35:
                risk_flags.append(
                    {
                        "category": "basis_dislocation",
                        "severity": "high",
                        "value": basis_bps,
                        "description": "Mark/index basis dislocation detected.",
                    }
                )
            elif abs(basis_bps) >= 20:
                risk_flags.append(
                    {
                        "category": "basis_stretched",
                        "severity": "medium",
                        "value": basis_bps,
                        "description": "Basis is stretched; watch mean-reversion risk.",
                    }
                )

        oi_change = self._safe_float((payload.get("open_interest") or {}).get("oi_change_5m_pct"))
        if oi_change is not None:
            if abs(oi_change) >= 5:
                risk_flags.append(
                    {
                        "category": "oi_spike",
                        "severity": "high",
                        "value": oi_change,
                        "description": "Open interest changed sharply in short window.",
                    }
                )
            elif abs(oi_change) >= 3:
                risk_flags.append(
                    {
                        "category": "oi_acceleration",
                        "severity": "medium",
                        "value": oi_change,
                        "description": "Open interest is accelerating.",
                    }
                )

        ls_ratio = self._safe_float((payload.get("liquidation_data") or {}).get("long_short_ratio"))
        if ls_ratio is not None:
            if ls_ratio >= 1.9 or ls_ratio <= 0.53:
                risk_flags.append(
                    {
                        "category": "crowded_positioning",
                        "severity": "high",
                        "value": ls_ratio,
                        "description": "Positioning is crowded; liquidation cascades are more likely.",
                    }
                )
            elif ls_ratio >= 1.6 or ls_ratio <= 0.65:
                risk_flags.append(
                    {
                        "category": "positioning_imbalance",
                        "severity": "medium",
                        "value": ls_ratio,
                        "description": "Long/short positioning imbalance detected.",
                    }
                )

        payload["risk_flags"] = risk_flags

        high_risk = any(flag.get("severity") == "high" for flag in risk_flags)
        medium_count = sum(1 for flag in risk_flags if flag.get("severity") == "medium")
        if high_risk:
            payload["leverage_guidance"] = {
                "posture": "conservative",
                "max_leverage": 2,
                "reason": "high derivatives risk flags triggered",
            }
        elif medium_count >= 2:
            payload["leverage_guidance"] = {
                "posture": "moderate",
                "max_leverage": 3,
                "reason": "multiple medium-risk derivatives flags triggered",
            }
        else:
            payload["leverage_guidance"] = {
                "posture": "normal",
                "max_leverage": 3,
                "reason": "no extreme derivatives stress in current snapshot",
            }

        available_blocks = sum(
            payload.get(key) is not None
            for key in ("funding_rate", "open_interest", "basis_data", "liquidation_data")
        )
        if available_blocks >= 3 and not payload["errors"]:
            payload["status"] = "ok"
            return RoutedCapabilityResult(
                capability=capability,
                success=True,
                data=payload,
                provider="binance_futures_public",
                degraded=False,
            )
        if available_blocks >= 1:
            payload["status"] = "partial"
            return RoutedCapabilityResult(
                capability=capability,
                success=True,
                data=payload,
                provider="binance_futures_public",
                degraded=bool(payload["errors"]),
            )

        payload["status"] = "failed"
        return RoutedCapabilityResult(
            capability=capability,
            success=False,
            data=payload,
            provider="binance_futures_public",
            error="failed to fetch any derivatives blocks",
            degraded=True,
        )
