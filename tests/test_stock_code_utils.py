# -*- coding: utf-8 -*-
"""Tests for src/services/stock_code_utils.py (US-only product scope)."""

import pytest

from src.services.stock_code_utils import is_code_like, normalize_code


class TestIsCodeLike:
    def test_us_ticker(self):
        assert is_code_like("AAPL") is True
        assert is_code_like("MSFT") is True

    def test_us_ticker_with_dot(self):
        assert is_code_like("BRK.B") is True

    def test_us_future_yahoo_style(self):
        assert is_code_like("ES=F") is True

    def test_crypto_pair(self):
        assert is_code_like("BTCUSDT") is True

    def test_legacy_cn_hk_rejected(self):
        assert is_code_like("600519") is False
        assert is_code_like("600519.SH") is False
        assert is_code_like("HK00700") is False
        assert is_code_like("00700.HK") is False
        assert is_code_like("00700") is False

    def test_plain_text(self):
        assert is_code_like("贵州茅台") is False

    def test_empty(self):
        assert is_code_like("") is False


class TestNormalizeCode:
    def test_us_ticker(self):
        assert normalize_code("AAPL") == "AAPL"
        assert normalize_code("  nvda  ") == "NVDA"

    def test_us_class_b(self):
        assert normalize_code("brk.b") == "BRK.B"

    def test_legacy_cn_hk_returns_none(self):
        assert normalize_code("600519") is None
        assert normalize_code("600519.SH") is None
        assert normalize_code("HK00700") is None

    def test_empty_returns_none(self):
        assert normalize_code("") is None

    def test_plain_text_returns_none(self):
        assert normalize_code("贵州茅台") is None
