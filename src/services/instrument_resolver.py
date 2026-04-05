# -*- coding: utf-8 -*-
"""
交易标的输入解析器。

将 API 入参（`stock_code` / `symbol` + 可选 `asset_class`）解析为统一的
InstrumentSchema，便于下游在保持兼容的前提下逐步接入「按资产类型」的处理。
"""

from __future__ import annotations

import re
from typing import Optional

from src.schemas.instrument_schema import AssetClass, InstrumentSchema


_US_EQUITY_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
_US_FUTURE_YAHOO_RE = re.compile(r"^[A-Z0-9.\-]+=?F$")
_PERP_SUFFIX_RE = re.compile(r"(?:[-_/]PERP|PERP)$")
_CRYPTO_PAIR_RE = re.compile(r"^[A-Z0-9]{2,20}(?:USDT|USDC|USD|BTC|ETH)$")


def is_legacy_cn_hk_symbol(symbol: str) -> bool:
    """
    若字符串符合常见 A 股 / 港股 / 北交所代码形态则返回 True。

    供 API（配合拒收开关）与 ``main.py`` CLI 使用，以落实当前产品范围：
    美股 / 期货 / 加密永续等。
    """
    return _looks_cn_or_hk_symbol(symbol)


def _looks_cn_or_hk_symbol(symbol: str) -> bool:
    """识别本轮重构中有意排除的 A 股 / 港股等代码形态。"""
    s = (symbol or "").strip().upper()
    if not s:
        return False
    if s.isdigit() and len(s) in (5, 6):
        return True
    if s.startswith(("SH", "SZ", "BJ")) and s[2:].isdigit():
        return True
    if s.startswith("HK") and s[2:].isdigit():
        return True
    if s.endswith((".SH", ".SZ", ".SS", ".BJ", ".HK")):
        return True
    return False


def _infer_asset_class(symbol: str) -> AssetClass:
    s = symbol.upper()
    if _PERP_SUFFIX_RE.search(s):
        return AssetClass.PERPETUAL
    if _US_FUTURE_YAHOO_RE.fullmatch(s):
        return AssetClass.FUTURE
    # 交易所返回的永续合约形态可能模糊；若无显式 asset_class，加密币对已按永续处理。
    if _CRYPTO_PAIR_RE.fullmatch(s):
        return AssetClass.PERPETUAL
    return AssetClass.US_EQUITY


def _default_session_mode(asset_class: AssetClass) -> str:
    if asset_class == AssetClass.US_EQUITY:
        return "us_equity_session"
    if asset_class == AssetClass.FUTURE:
        return "futures_session"
    return "always_open_24x7"


def _default_contract_type(asset_class: AssetClass) -> str:
    if asset_class == AssetClass.US_EQUITY:
        return "equity"
    if asset_class == AssetClass.FUTURE:
        return "future"
    return "perpetual"


def resolve_instrument_input(
    *,
    stock_code: Optional[str] = None,
    symbol: Optional[str] = None,
    asset_class: Optional[str] = None,
    exchange: Optional[str] = None,
    reject_cn_hk: bool = True,
) -> InstrumentSchema:
    """
    将原始请求字段解析为规范化的 instrument 对象。

    优先级：
    1. 显式传入的 `symbol`
    2. 否则回退到兼容字段 `stock_code`
    """
    raw_symbol = (symbol or stock_code or "").strip().upper()
    if not raw_symbol:
        raise ValueError("symbol or stock_code is required")

    if reject_cn_hk and is_legacy_cn_hk_symbol(raw_symbol):
        raise ValueError(
            "CN/HK symbols are no longer accepted in this analysis path; "
            "please use US equities / futures / perpetual symbols."
        )

    if asset_class:
        try:
            resolved_asset_class = AssetClass(asset_class.strip().lower())
        except ValueError as exc:
            raise ValueError(f"unsupported asset_class: {asset_class}") from exc
    else:
        resolved_asset_class = _infer_asset_class(raw_symbol)

    if resolved_asset_class == AssetClass.US_EQUITY and not _US_EQUITY_TICKER_RE.fullmatch(raw_symbol):
        raise ValueError(f"invalid us_equity symbol format: {raw_symbol}")

    instrument = InstrumentSchema(
        asset_class=resolved_asset_class,
        symbol=raw_symbol,
        exchange=(exchange or "").strip().upper() or None,
        contract_type=_default_contract_type(resolved_asset_class),
        is_perpetual=resolved_asset_class == AssetClass.PERPETUAL,
        session_mode=_default_session_mode(resolved_asset_class),
    )
    return instrument


def instrument_to_legacy_code(instrument: InstrumentSchema) -> str:
    """
    将 instrument 转为当前遗留管线使用的主键字符串。

    现有管线/服务层仍以 `stock_code` 为索引；本函数在渐进迁移时把规范 symbol
    从统一入口带到旧代码路径。
    """
    return instrument.symbol

