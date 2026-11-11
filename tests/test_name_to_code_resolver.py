# -*- coding: utf-8 -*-
"""Tests for name_to_code_resolver (US-only STOCK_NAME_MAP)."""

import pytest

from src.services.name_to_code_resolver import (
    resolve_name_to_code,
    _build_reverse_map_no_duplicates,
)


class TestBuildReverseMapNoDuplicates:
    def test_excludes_ambiguous_names(self):
        code_to_name = {"BABA": "阿里巴巴", "BIDU": "百度", "AAPL": "苹果"}
        result = _build_reverse_map_no_duplicates(code_to_name)
        assert result.get("苹果") == "AAPL"
        assert result.get("百度") == "BIDU"

    def test_includes_unique_names(self):
        code_to_name = {"AAPL": "苹果", "NVDA": "英伟达"}
        result = _build_reverse_map_no_duplicates(code_to_name)
        assert result["苹果"] == "AAPL"
        assert result["英伟达"] == "NVDA"


class TestResolveNameToCode:
    def test_code_like_input_returned_normalized(self):
        assert resolve_name_to_code("  AAPL  ") == "AAPL"
        assert resolve_name_to_code("brk.b") == "BRK.B"

    def test_legacy_cn_hk_code_rejected(self):
        assert resolve_name_to_code("600519") is None
        assert resolve_name_to_code("600519.SH") is None
        assert resolve_name_to_code("HK00700") is None

    def test_local_map_exact_match(self):
        assert resolve_name_to_code("苹果") == "AAPL"
        assert resolve_name_to_code("英伟达") == "NVDA"

    def test_returns_none_for_empty_or_invalid_input(self):
        assert resolve_name_to_code("") is None
        assert resolve_name_to_code("   ") is None
        assert resolve_name_to_code(None) is None  # type: ignore

    def test_returns_none_when_no_match(self):
        result = resolve_name_to_code("不存在的股票名称xyz")
        assert result is None

    def test_skips_fuzzy_for_non_cjk_garbage_input(self):
        result = resolve_name_to_code("not-a-valid-ticker!!!")
        assert result is None
