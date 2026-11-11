# -*- coding: utf-8 -*-
"""
===================================
名称到代码解析
===================================

将股票名称解析为代码：本地映射 + 拼音 + 模糊匹配。
随 A 股抓取器移除，已不再使用 AkShare 在线 A 股列表兜底。
"""

from __future__ import annotations

import difflib
import logging
from typing import Dict, Optional, Set, Tuple

from src.data.stock_mapping import STOCK_NAME_MAP
from src.services.instrument_resolver import is_legacy_cn_hk_symbol
from src.services.stock_code_utils import is_code_like, normalize_code

logger = logging.getLogger(__name__)


def _contains_cjk(text: str) -> bool:
    """若字符串含中日韩统一表意文字则返回 True。"""
    return any("\u3400" <= ch <= "\u9fff" for ch in text)


def _is_code_like(s: str) -> bool:
    """兼容层：转调共享的「是否像代码」判定。"""
    return is_code_like(s)


def _normalize_code(raw: str) -> Optional[str]:
    """兼容层：转调共享的代码规范化。"""
    return normalize_code(raw)


def _build_reverse_map_no_duplicates(
    code_to_name: Dict[str, str],
) -> Dict[str, str]:
    """
    构建 名称 -> 代码 映射；一名多码（歧义）的名称不纳入。
    """
    name_to_codes: Dict[str, Set[str]] = {}
    for code, name in code_to_name.items():
        if not name or not code:
            continue
        name = name.strip()
        if name not in name_to_codes:
            name_to_codes[name] = set()
        name_to_codes[name].add(code)
    # 仅保留恰好对应单一代码的名称
    return {name: next(iter(codes)) for name, codes in name_to_codes.items() if len(codes) == 1}


def _build_local_name_indexes(code_to_name: Dict[str, str]) -> Tuple[Dict[str, str], Set[str]]:
    """
    构建本地缓存索引：
    - 唯一名称 -> 代码
    - 歧义名称集合（应快速返回失败）
    """
    name_to_codes: Dict[str, Set[str]] = {}
    for code, name in code_to_name.items():
        if not name or not code:
            continue
        normalized_name = name.strip()
        if not normalized_name:
            continue
        name_to_codes.setdefault(normalized_name, set()).add(code)

    unique_names = {
        name: next(iter(codes))
        for name, codes in name_to_codes.items()
        if len(codes) == 1
    }
    ambiguous_names = {
        name
        for name, codes in name_to_codes.items()
        if len(codes) > 1
    }
    return unique_names, ambiguous_names


_LOCAL_REVERSE_MAP, _LOCAL_AMBIGUOUS_NAMES = _build_local_name_indexes(STOCK_NAME_MAP)


def _is_single_char_typo(input_name: str, candidate_name: str) -> bool:
    """两个名称是否仅有一处字符不同。"""
    if not input_name or not candidate_name:
        return False
    if len(input_name) != len(candidate_name):
        return False
    # 笔误兜底保守：名称过短则不对齐
    if len(input_name) < 3:
        return False
    diff = sum(1 for a, b in zip(input_name, candidate_name) if a != b)
    return diff == 1


def resolve_name_to_code(name: str) -> Optional[str]:
    """
    将股票名称解析为代码。

    策略（顺序）:
    1. 输入形似美股/期货/永续代码则规范化后返回（拒收 A 股 / 港股形态）。
    2. 本地 STOCK_NAME_MAP 反向表（排除歧义名）。
    3. 与本地名称做拼音精确匹配。
    4. 仅在本地映射上做模糊匹配（difflib）。
    5. 失败返回 None。

    参数:
        name: 股票名称或代码字符串。

    返回:
        解析得到的代码；歧义或失败则为 None。
    """
    if not name or not isinstance(name, str):
        return None
    s = name.strip()
    if not s:
        return None

    # 1. 输入形似代码
    if _is_code_like(s):
        normalized = _normalize_code(s)
        if normalized and is_legacy_cn_hk_symbol(normalized):
            return None
        return normalized

    # 2. 本地反向表（已去重）
    local_reverse = _LOCAL_REVERSE_MAP
    if s in local_reverse:
        return local_reverse[s]
    if s in _LOCAL_AMBIGUOUS_NAMES:
        logger.debug(f"[NameResolver] 命中本地歧义名称，快速返回 None: {s}")
        return None

    # 3. 拼音匹配（精确）
    try:
        from pypinyin import lazy_pinyin

        input_pinyin = "".join(lazy_pinyin(s)).lower()
        for local_name, code in local_reverse.items():
            local_pinyin = "".join(lazy_pinyin(local_name)).lower()
            if input_pinyin == local_pinyin:
                return code
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"[NameResolver] Pinyin match failed: {e}")

    # 非 CJK 自由文本（如无意义拉丁串）不做模糊兜底
    if not _contains_cjk(s):
        logger.debug(f"[NameResolver] Skip CJK-only fallbacks for non-CJK input: {s}")
        return None

    # 4. 模糊匹配（仅本地）
    all_name_to_code = dict(local_reverse)
    if len(s) > 2:
        names = list(all_name_to_code.keys())
        matches = difflib.get_close_matches(s, names, n=1, cutoff=0.8)
        if matches:
            logger.debug(f"[NameResolver] 命中模糊匹配: input={s}, matched={matches[0]}")
            return all_name_to_code[matches[0]]

        typo_matches = difflib.get_close_matches(s, names, n=1, cutoff=0.7)
        if typo_matches and _is_single_char_typo(s, typo_matches[0]):
            logger.debug(f"[NameResolver] 命中单字误写兜底: input={s}, matched={typo_matches[0]}")
            return all_name_to_code[typo_matches[0]]

    logger.debug(f"[NameResolver] 解析失败: {s}")
    return None
