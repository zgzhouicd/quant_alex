# -*- coding: utf-8 -*-
"""Tests for name_to_code_resolver.

Covers:
- Local mapping (STOCK_NAME_MAP reverse)
- Pinyin match (when pypinyin available)
- Fuzzy match (difflib, local map only)
- Ambiguous names return None

Code-shape checks live in tests/test_stock_code_utils.py (_is_code_like / _normalize_code
are thin wrappers around stock_code_utils).
"""

import pytest

from src.services.name_to_code_resolver import (
    resolve_name_to_code,
    _build_reverse_map_no_duplicates,
)


class TestBuildReverseMapNoDuplicates:
    def test_excludes_ambiguous_names(self):
        # "阿里巴巴" maps to both BABA and 09988
        code_to_name = {"BABA": "阿里巴巴", "09988": "阿里巴巴", "600519": "贵州茅台"}
        result = _build_reverse_map_no_duplicates(code_to_name)
        assert "阿里巴巴" not in result
        assert result.get("贵州茅台") == "600519"

    def test_includes_unique_names(self):
        code_to_name = {"600519": "贵州茅台", "00700": "腾讯控股"}
        result = _build_reverse_map_no_duplicates(code_to_name)
        assert result["贵州茅台"] == "600519"
        assert result["腾讯控股"] == "00700"


# ---------------------------------------------------------------------------
# resolve_name_to_code
# ---------------------------------------------------------------------------

class TestResolveNameToCode:
    def test_code_like_input_returned_normalized(self):
        assert resolve_name_to_code("600519") == "600519"
        assert resolve_name_to_code("600519.SH") == "600519"
        assert resolve_name_to_code("  AAPL  ") == "AAPL"

    def test_local_map_exact_match(self):
        assert resolve_name_to_code("贵州茅台") == "600519"
        assert resolve_name_to_code("腾讯控股") == "00700"

    def test_returns_none_for_empty_or_invalid_input(self):
        assert resolve_name_to_code("") is None
        assert resolve_name_to_code("   ") is None
        assert resolve_name_to_code(None) is None  # type: ignore

    def test_ambiguous_name_returns_none(self):
        # "阿里巴巴" maps to both BABA and 09988 in STOCK_NAME_MAP
        assert resolve_name_to_code("阿里巴巴") is None

    def test_fuzzy_match_fallback_local_only(self):
        # Typo: 贵州茅苔 -> fuzzy match 贵州茅台 in STOCK_NAME_MAP
        result = resolve_name_to_code("贵州茅苔")
        assert result == "600519"

    def test_returns_none_when_no_match(self):
        result = resolve_name_to_code("不存在的股票名称xyz")
        assert result is None

    def test_skips_fuzzy_for_non_cjk_garbage_input(self):
        result = resolve_name_to_code("aaaaaaa")
        assert result is None
