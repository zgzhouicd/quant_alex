# -*- coding: utf-8 -*-
"""
股票代码相关的共享工具函数。
"""

from __future__ import annotations

import re
from typing import Optional


# 已知交易所前缀（大小写不敏感）及其允许的纯数字位数。
# 例：SH600519 -> 600519，HK00700 -> 00700
_PREFIX_DIGIT_LENS: dict = {
    "SH": (6,),
    "SZ": (6,),
    "SS": (6,),
    "HK": (1, 2, 3, 4, 5),
}

_SUFFIX_DIGIT_LENS: dict = {
    ".SH": (6,),
    ".SZ": (6,),
    ".SS": (6,),
    ".HK": (1, 2, 3, 4, 5),
}


def _strip_exchange_prefix(text: str) -> Optional[str]:
    """去掉首部交易所前缀（SH/SZ/HK 等），返回规范后的数字串；不匹配则 None。"""
    for prefix, digit_lens in _PREFIX_DIGIT_LENS.items():
        if text.startswith(prefix):
            base = text[len(prefix):]
            if base.isdigit() and len(base) in digit_lens:
                return base.zfill(5) if prefix == "HK" else base
    return None


def _strip_exchange_suffix(text: str) -> Optional[str]:
    """去掉尾部交易所后缀（.SH/.SZ/.SS/.HK），返回规范后的数字串；不匹配则 None。"""
    for suffix, digit_lens in _SUFFIX_DIGIT_LENS.items():
        if text.endswith(suffix):
            base = text[: -len(suffix)].strip()
            if base.isdigit() and len(base) in digit_lens:
                return base.zfill(5) if suffix == ".HK" else base
    return None


def is_code_like(value: str) -> bool:
    """判断字符串是否像股票/标的代码（5–6 位数字、1–5 位字母、或带交易所前后缀）。"""
    text = value.strip().upper()
    if not text:
        return False
    if text.isdigit() and len(text) in (5, 6):
        return True
    if _strip_exchange_suffix(text) is not None:
        return True
    if re.match(r"^[A-Z]{1,5}(?:\.(?:US|[A-Z]))?$", text):
        return True
    # 支持交易所前缀：SH600519、SZ000001、HK00700
    if _strip_exchange_prefix(text) is not None:
        return True
    return False


def normalize_code(raw: str) -> Optional[str]:
    """归一化并校验单个股票/标的代码。

    支持：
    - 纯数字：600519、00700
    - 后缀形式：600519.SH、600519.SZ、00700.HK
    - 前缀形式：SH600519、SZ000001、HK00700（大小写不敏感）
    - 美股代码：AAPL、TSLA
    """
    text = raw.strip().upper()
    if not text:
        return None
    if text.isdigit() and len(text) in (5, 6):
        return text
    if re.match(r"^[A-Z]{1,5}(?:\.(?:US|[A-Z]))?$", text):
        return text
    stripped_suffix = _strip_exchange_suffix(text)
    if stripped_suffix is not None:
        return stripped_suffix
    # 交易所前缀：SH600519 -> 600519，HK00700 -> 00700
    stripped = _strip_exchange_prefix(text)
    if stripped is not None:
        return stripped
    return None
