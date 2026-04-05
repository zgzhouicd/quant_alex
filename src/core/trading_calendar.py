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

时间与存储策略见 ``docs/timezone-policy.md``；UTC 辅助函数见 ``src.utils.timeutil``。
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta
from typing import Any, Optional, Set
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# exchange-calendars 是否已安装
_XCALS_AVAILABLE = False
try:
    import exchange_calendars as xcals
    _XCALS_AVAILABLE = True
except ImportError:
    logger.warning(
        "exchange-calendars not installed; trading day check disabled. "
        "Run: pip install exchange-calendars"
    )

# 市场 -> exchange-calendars 交易所代码
MARKET_EXCHANGE = {"cn": "XSHG", "hk": "XHKG", "us": "XNYS"}

# 市场 -> 判断「今日」用的 IANA 时区名
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
    由股票/标的代码推断市场区域。

    返回:
        'cn' | 'hk' | 'us' | None（None 表示未识别；fail-open：视为可交易）
    """
    if not code or not isinstance(code, str):
        return None
    code = (code or "").strip().upper()

    from data_provider import is_us_stock_code, is_us_index_code, is_hk_stock_code

    if is_us_stock_code(code) or is_us_index_code(code):
        return "us"
    if is_hk_stock_code(code):
        return "hk"
    # A 股：6 位纯数字
    if code.isdigit() and len(code) == 6:
        return "cn"

    from src.services.instrument_resolver import _infer_asset_class
    from src.schemas.instrument_schema import AssetClass

    inferred = _infer_asset_class(code)
    if inferred == AssetClass.FUTURE:
        return "us"
    if inferred == AssetClass.PERPETUAL:
        return None
    return None


def is_market_open(market: str, check_date: date) -> bool:
    """
    判断指定市场在指定日期是否为交易日。

    fail-open：未安装 exchange-calendars 或日期越界等情况返回 True。

    参数:
        market: 'cn' | 'hk' | 'us'
        check_date: 待判断日期

    返回:
        交易日为 True（含 fail-open）；否则 False
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
    返回该市场本地时区的当前时间。

    若 current_time 为 naive，则视为已是该市场时区下的本地时间。
    未知市场则回退为传入时间（未传则系统本地时间）。
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
    解析可用于 checkpoint / 续跑逻辑的「日 K 所用交易日」。

    规则概要:
    - 非交易日 / 节假日：取上一交易日
    - 交易盘中（未收盘）：上一完整交易日
    - 收盘后：当前交易日
    - 日历查询失败：fail-open，使用该市场自然日
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


def normalize_checkpoint_date_for_stock(code: str, target_date: date) -> date:
    """
    将公历日对齐到续跑所用的日 K 会话日。

    在该标的所在市场时区取当日 23:59 为锚点，使周末/节假日映射到有效会话日
    （与 :func:`get_effective_trading_date` 同一套规则）。
    """
    market = get_market_for_stock((code or "").strip())
    tz_name = MARKET_TIMEZONE.get(market or "")
    if not tz_name:
        return target_date
    try:
        anchor = datetime.combine(target_date, dt_time(23, 59), tzinfo=ZoneInfo(tz_name))
    except Exception:
        return target_date
    return get_effective_trading_date(market, current_time=anchor)


def get_open_markets_today() -> Set[str]:
    """
    按各市场本地时区，返回「今日开市」的市场集合。

    返回:
        今日交易中的市场键集合（'cn' | 'hk' | 'us'）
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
    """单个标的解析后的交易时段状态。"""

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
    按标的解析交易时段状态（供编排与调度使用）。

    支持的模式:
    - us_equity_session：盘前 / 常规 / 盘后 / 关闭
    - futures_session：日盘 / 夜盘 / 日盘间歇 / 周末
    - always_open_24x7：连续交易
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

    # 期货会话（futures_session）
    local_time = now_local.time()
    weekday = now_local.weekday()  # 周一=0 … 周日=6

    # 周末休市：约周五 17:00 -> 周日 18:00（美东粗略近似）
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
    """由标的的会话模型解析 checkpoint 目标日期。"""
    state = resolve_session_state(
        instrument,
        current_time=current_time,
        fallback_market=fallback_market,
    )
    return state.effective_date
