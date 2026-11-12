# -*- coding: utf-8 -*-
"""
数据源基类与管理器（兼容导入路径 `data_provider.base`）。

实现分布在：
- `base_fetcher.py` — BaseFetcher
- `fetcher_manager.py` — DataFetcherManager
- `errors.py` / `symbol_normalize.py`
"""

from data_provider.base_fetcher import (  # noqa: F401
    INTRADAY_STANDARD_COLUMNS,
    STANDARD_COLUMNS,
    BaseFetcher,
)
from data_provider.fetcher_manager import DataFetcherManager  # noqa: F401
from data_provider.errors import (  # noqa: F401
    DataFetchError,
    DataSourceUnavailableError,
    RateLimitError,
)
from data_provider.symbol_normalize import (  # noqa: F401
    ETF_PREFIXES,
    _is_etf_code,
    _is_hk_market,
    _is_us_market,
    _market_tag,
    canonical_stock_code,
    is_bse_code,
    is_kc_cy_stock,
    is_st_stock,
    normalize_stock_code,
    summarize_exception,
    unwrap_exception,
)

__all__ = [
    "STANDARD_COLUMNS",
    "INTRADAY_STANDARD_COLUMNS",
    "BaseFetcher",
    "DataFetcherManager",
    "DataFetchError",
    "RateLimitError",
    "DataSourceUnavailableError",
    "normalize_stock_code",
    "canonical_stock_code",
    "unwrap_exception",
    "summarize_exception",
]
