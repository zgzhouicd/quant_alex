# -*- coding: utf-8 -*-
"""Shared US-market symbols and labels for tests (product scope: no A-share/HK tickers)."""

SAMPLE_TICKERS = ("AAPL", "MSFT", "NVDA", "TSLA")
SAMPLE_TICKER = SAMPLE_TICKERS[0]
SAMPLE_NAME_ZH = "苹果公司"
SAMPLE_NAME_ZH_MSFT = "微软"
SAMPLE_BATCH = list(SAMPLE_TICKERS[:2])

# Legacy CN/HK examples — use only in tests that assert *rejection*, not success paths.
LEGACY_CN_CODE = "600519"
LEGACY_HK_CODE = "00700"
