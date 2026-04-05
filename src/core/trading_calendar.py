# -*- coding: utf-8 -*-
"""
===================================
交易日历模块 (Issue #373)
===================================

职责：
1. 按市场（A股/港股/美股）判断当日是否为交易日
2. 按市场时区取“今日”日期，避免服务器 UTC 导致日期错误
3. 支持 per-stock 过滤：只分析当日开市市场的股票

依赖：exchange-calendars（可选，不可用时 fail-open）
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta
from typing import Any, Optional, Set
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Exchange-calendars availability
_XCALS_AVAILABLE = False
try:
    import exchange_calendars as xcals
    _XCALS_AVAILABLE = True
except ImportError:
    logger.warning(
        "exchange-calendars not installed; trading day check disabled. "
        "Run: pip install exchange-calendars"
    )

# Market -> exchange code (exchange-calendars)
MARKET_EXCHANGE = {"cn": "XSHG", "hk": "XHKG", "us": "XNYS"}

# Market -> IANA timezone for "today"
MARKET_TIMEZONE = {
    "cn": "Asia/Shanghai",
    "hk": "Asia/Hong_Kong",
    "us": "America/New_York",
}

SESSION_MODE_TIMEZONE = {
    "us_equity_session": "America/New_York",
    "futures_session": "America/New_York",
    "always_open_24x7": "UTC",
}


def get_market_for_stock(code: str) -> Optional[str]:
    """
    Infer market region for a stock code.

    Returns:
        'cn' | 'hk' | 'us' | None (None = unrecognized, fail-open: treat as open)
    """
    if not code or not isinstance(code, str):
        return None
    code = (code or "").strip().upper()

    from data_provider import is_us_stock_code, is_us_index_code, is_hk_stock_code

    if is_us_stock_code(code) or is_us_index_code(code):
        return "us"
    if is_hk_stock_code(code):
        return "hk"
    # A-share: 6-digit numeric
    if code.isdigit() and len(code) == 6:
        return "cn"
    return None


def is_market_open(market: str, check_date: date) -> bool:
    """
    Check if the given market is open on the given date.

    Fail-open: returns True if exchange-calendars unavailable or date out of range.

    Args:
        market: 'cn' | 'hk' | 'us'
        check_date: Date to check

    Returns:
        True if trading day (or fail-open), False otherwise
    """
    if not _XCALS_AVAILABLE:
        return True
    ex = MARKET_EXCHANGE.get(market)
    if not ex:
        return True
    try:
        cal = xcals.get_calendar(ex)
        session = datetime(check_date.year, check_date.month, check_date.day)
        return cal.is_session(session)
    except Exception as e:
        logger.warning("trading_calendar.is_market_open fail-open: %s", e)
        return True


def get_market_now(
    market: Optional[str], current_time: Optional[datetime] = None
) -> datetime:
    """
    Return current time in the market's local timezone.

    If current_time is naive, treat it as already expressed in the market timezone.
    Unknown markets fall back to the given datetime (or local system time).
    """
    tz_name = MARKET_TIMEZONE.get(market or "")

    if current_time is None:
        if tz_name:
            return datetime.now(ZoneInfo(tz_name))
        return datetime.now()

    if not tz_name:
        return current_time

    tz = ZoneInfo(tz_name)
    if current_time.tzinfo is None:
        return current_time.replace(tzinfo=tz)
    return current_time.astimezone(tz)


def get_effective_trading_date(
    market: Optional[str], current_time: Optional[datetime] = None
) -> date:
    """
    Resolve the latest reusable daily-bar date for checkpoint/resume logic.

    Rules:
    - Non-trading day / holiday: previous trading session
    - Trading day before market close: previous completed trading session
    - Trading day after market close: current trading session
    - Calendar lookup failure: fail-open to market-local natural date
    """
    market_now = get_market_now(market, current_time=current_time)
    fallback_date = market_now.date()

    if not _XCALS_AVAILABLE:
        return fallback_date

    ex = MARKET_EXCHANGE.get(market or "")
    tz_name = MARKET_TIMEZONE.get(market or "")
    if not ex or not tz_name:
        return fallback_date

    try:
        cal = xcals.get_calendar(ex)
        local_date = market_now.date()

        if not cal.is_session(local_date):
            return cal.date_to_session(local_date, direction="previous").date()

        session = cal.date_to_session(local_date, direction="previous")
        session_close = cal.session_close(session)
        if hasattr(session_close, "tz_convert"):
            close_local = session_close.tz_convert(tz_name).to_pydatetime()
        elif session_close.tzinfo is not None:
            close_local = session_close.astimezone(ZoneInfo(tz_name))
        else:
            close_local = session_close.replace(tzinfo=ZoneInfo(tz_name))

        if market_now >= close_local:
            return session.date()

        return cal.previous_session(session).date()
    except Exception as e:
        logger.warning("trading_calendar.get_effective_trading_date fail-open: %s", e)
        return fallback_date


def get_open_markets_today() -> Set[str]:
    """
    Get markets that are open today (by each market's local timezone).

    Returns:
        Set of market keys ('cn', 'hk', 'us') that are trading today
    """
    if not _XCALS_AVAILABLE:
        return {"cn", "hk", "us"}
    result: Set[str] = set()
    for mkt, tz_name in MARKET_TIMEZONE.items():
        try:
            tz = ZoneInfo(tz_name)
            today = datetime.now(tz).date()
            if is_market_open(mkt, today):
                result.add(mkt)
        except Exception as e:
            logger.warning("get_open_markets_today fail-open for %s: %s", mkt, e)
            result.add(mkt)
    return result


def compute_effective_region(
    config_region: str, open_markets: Set[str]
) -> Optional[str]:
    """
    US-only market recap gate: run recap when the US cash session is open.

    A股/港股复盘已移除；config_region 仅保留参数兼容，结果只依赖 ``us`` 是否开市。

    Returns:
        None: 调用方关闭交易日校验（force_run 等），复盘照常尝试执行
        '': 当日美股休市，跳过大盘复盘
        'us': 当日美股开市，执行美股复盘
    """
    _ = (config_region or "us").strip().lower()
    return "us" if "us" in open_markets else ""


@dataclass
class SessionState:
    """Resolved market session state for a single instrument."""

    session_mode: str
    is_open: bool
    phase: str
    now: datetime
    effective_date: date


def _resolve_session_mode(
    instrument: Optional[dict],
    *,
    fallback_market: Optional[str] = None,
) -> str:
    session_mode = str((instrument or {}).get("session_mode") or "").strip().lower()
    if session_mode in SESSION_MODE_TIMEZONE:
        return session_mode

    asset_class = str((instrument or {}).get("asset_class") or "").strip().lower()
    if asset_class == "perpetual":
        return "always_open_24x7"
    if asset_class == "future":
        return "futures_session"
    if asset_class == "us_equity":
        return "us_equity_session"

    if fallback_market == "us":
        return "us_equity_session"
    return "always_open_24x7"


def _get_session_now(session_mode: str, current_time: Optional[datetime] = None) -> datetime:
    tz_name = SESSION_MODE_TIMEZONE.get(session_mode, "UTC")
    if current_time is None:
        return datetime.now(ZoneInfo(tz_name))
    if current_time.tzinfo is None:
        return current_time.replace(tzinfo=ZoneInfo(tz_name))
    return current_time.astimezone(ZoneInfo(tz_name))


def resolve_session_state(
    instrument: Optional[dict],
    *,
    current_time: Optional[datetime] = None,
    fallback_market: Optional[str] = None,
) -> SessionState:
    """
    Resolve market session state for instrument-aware scheduling.

    Supported modes:
    - us_equity_session: pre/regular/post/closed
    - futures_session: day/night/daily_break/weekend
    - always_open_24x7: continuous
    """
    session_mode = _resolve_session_mode(instrument, fallback_market=fallback_market)
    now_local = _get_session_now(session_mode, current_time=current_time)

    if session_mode == "always_open_24x7":
        return SessionState(
            session_mode=session_mode,
            is_open=True,
            phase="continuous",
            now=now_local,
            effective_date=now_local.date(),
        )

    if session_mode == "us_equity_session":
        local_date = now_local.date()
        trade_day = is_market_open("us", local_date)
        local_time = now_local.time()
        if not trade_day:
            phase = "closed"
            is_open = False
        elif dt_time(4, 0) <= local_time < dt_time(9, 30):
            phase = "pre_market"
            is_open = True
        elif dt_time(9, 30) <= local_time < dt_time(16, 0):
            phase = "regular"
            is_open = True
        elif dt_time(16, 0) <= local_time < dt_time(20, 0):
            phase = "post_market"
            is_open = True
        else:
            phase = "closed"
            is_open = False

        effective_date = get_effective_trading_date("us", current_time=now_local)
        return SessionState(
            session_mode=session_mode,
            is_open=is_open,
            phase=phase,
            now=now_local,
            effective_date=effective_date,
        )

    # futures_session
    local_time = now_local.time()
    weekday = now_local.weekday()  # Monday=0 ... Sunday=6

    # Weekend close: Fri 17:00 -> Sun 18:00 (ET approximation)
    if (weekday == 4 and local_time >= dt_time(17, 0)) or weekday == 5 or (
        weekday == 6 and local_time < dt_time(18, 0)
    ):
        phase = "weekend"
        is_open = False
    elif dt_time(17, 0) <= local_time < dt_time(18, 0):
        phase = "daily_break"
        is_open = False
    elif dt_time(8, 0) <= local_time < dt_time(17, 0):
        phase = "day_session"
        is_open = True
    else:
        phase = "night_session"
        is_open = True

    effective_date = now_local.date()
    if phase == "weekend":
        if weekday == 5:
            effective_date = now_local.date() - timedelta(days=1)
        elif weekday == 6 and local_time < dt_time(18, 0):
            effective_date = now_local.date() - timedelta(days=2)

    return SessionState(
        session_mode=session_mode,
        is_open=is_open,
        phase=phase,
        now=now_local,
        effective_date=effective_date,
    )


def resolve_effective_date_by_instrument(
    instrument: Optional[dict],
    *,
    current_time: Optional[datetime] = None,
    fallback_market: Optional[str] = None,
) -> date:
    """Resolve checkpoint target date from instrument session model."""
    state = resolve_session_state(
        instrument,
        current_time=current_time,
        fallback_market=fallback_market,
    )
    return state.effective_date
