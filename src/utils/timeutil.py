# -*- coding: utf-8 -*-
"""
时区与时间相关的轻量辅助函数。

与「市场本地日/会话」相关的政策见 ``docs/timezone-policy.md``；本模块仅提供 UTC 等通用时刻。
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """返回当前时刻的 **UTC、带 tzinfo** 的 datetime（非 naive）。"""
    return datetime.now(timezone.utc)
