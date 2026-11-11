# -*- coding: utf-8 -*-
"""
股票代码相关的共享工具函数（美股 / 美期货 / 加密永续等，不含 A 股与港股形态）。
"""

from __future__ import annotations

import re
from typing import Optional

from src.services.instrument_resolver import is_legacy_cn_hk_symbol

_US_EQUITY_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
_US_FUTURE_YAHOO_RE = re.compile(r"^[A-Z0-9.\-]+=?F$")
_CRYPTO_PAIR_RE = re.compile(r"^[A-Z0-9]{2,20}(?:USDT|USDC|USD|BTC|ETH)$")
_PERP_SUFFIX_RE = re.compile(r"(?:[-_/]PERP|PERP)$", re.IGNORECASE)


def _looks_like_supported_symbol(text: str) -> bool:
    upper = text.strip().upper()
    if not upper or is_legacy_cn_hk_symbol(upper):
        return False
    if _US_FUTURE_YAHOO_RE.fullmatch(upper):
        return True
    if _CRYPTO_PAIR_RE.fullmatch(upper):
        return True
    if _PERP_SUFFIX_RE.search(upper):
        return True
    return _US_EQUITY_TICKER_RE.fullmatch(upper) is not None


def is_code_like(value: str) -> bool:
    """判断字符串是否像本产品支持的标的代码。"""
    return _looks_like_supported_symbol(value or "")


def normalize_code(raw: str) -> Optional[str]:
    """归一化并校验单个标的代码；不支持 A 股 / 港股形态。"""
    text = (raw or "").strip().upper()
    if not text:
        return None
    if not _looks_like_supported_symbol(text):
        return None
    return text
