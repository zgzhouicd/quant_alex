# -*- coding: utf-8 -*-
"""Static product capability tiers for health/API (support expectations management)."""

from __future__ import annotations

from typing import Any, Dict

# stable | beta | experimental
PRODUCT_CAPABILITIES: Dict[str, str] = {
    "market_scope": "stable",  # US equities / US futures / crypto perps
    "daily_analysis": "stable",
    "decision_desk_intraday": "stable",
    "agent_ask": "stable",
    "backtest_next_day": "stable",
    "stock_autocomplete": "beta",
    "image_import": "beta",
    "paper_trading_api": "experimental",
    "bot_nl_routing": "experimental",
}


def get_product_capabilities() -> Dict[str, Any]:
    return {
        "items": dict(PRODUCT_CAPABILITIES),
        "note": "stable=主路径；beta=可用但迭代中；experimental=需显式开启或仅 API",
    }
