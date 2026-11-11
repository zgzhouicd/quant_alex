# -*- coding: utf-8 -*-
"""分钟级日内信号与调度的产品默认参数（Web / API / CLI 对齐）。"""

from __future__ import annotations

DEFAULT_INTRADAY_INTERVAL = "5m"
DEFAULT_LOOKBACK_MINUTES = 390
DEFAULT_POLL_SECONDS = 60
DEFAULT_DAILY_LOOKBACK_DAYS = 120

SUPPORTED_MINUTE_INTERVALS = ("1m", "5m", "15m", "30m", "60m")


def is_daily_interval(interval: str) -> bool:
    text = (interval or "").strip().lower()
    return text in {"1d", "d", "day", "daily", "1day"}
