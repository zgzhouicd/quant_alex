# -*- coding: utf-8 -*-
"""
数据源策略层：国际行情（Yahoo Finance + 长桥兜底）。

原 A 股 / 港股专用 fetcher（AkShare、Tushare、eFinance 等）已移除，以缩减代码体积；
如需恢复请从历史版本或分支取回对应模块并 ``DataFetcherManager.add_fetcher()`` 注册。
"""

from .base import BaseFetcher, DataFetcherManager
from .binance_public_fetcher import BinancePublicFetcher, binance_spot_symbol_for_intraday
from .yfinance_fetcher import YfinanceFetcher
from .longbridge_fetcher import LongbridgeFetcher
from .us_index_mapping import (
    is_us_index_code,
    is_us_stock_code,
    is_hk_stock_code,
    get_us_index_yf_symbol,
    US_INDEX_MAPPING,
)

__all__ = [
    'BaseFetcher',
    'DataFetcherManager',
    'BinancePublicFetcher',
    'binance_spot_symbol_for_intraday',
    'YfinanceFetcher',
    'LongbridgeFetcher',
    'is_us_index_code',
    'is_us_stock_code',
    'is_hk_stock_code',
    'get_us_index_yf_symbol',
    'US_INDEX_MAPPING',
]
