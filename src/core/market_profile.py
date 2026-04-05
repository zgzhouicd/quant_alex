# -*- coding: utf-8 -*-
"""
大盘复盘 — 美股指数与宏观叙事（A股/港股复盘已移除）
"""

from dataclasses import dataclass
from typing import List


@dataclass
class MarketProfile:
    """US-focused daily recap profile (indices + search hooks)."""

    region: str
    mood_index_code: str
    news_queries: List[str]
    prompt_index_hint: str
    has_market_stats: bool
    has_sector_rankings: bool


US_PROFILE = MarketProfile(
    region="us",
    mood_index_code="SPX",
    news_queries=[
        "美股 大盘",
        "US stock market",
        "S&P 500 NASDAQ",
        "crypto futures market",
    ],
    prompt_index_hint="分析标普500、纳斯达克、道指等各指数走势特点",
    has_market_stats=False,
    has_sector_rankings=False,
)


def get_profile(region: str) -> MarketProfile:
    """Only US macro recap is supported; legacy cn/hk values map to US."""
    return US_PROFILE
