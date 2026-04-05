# -*- coding: utf-8 -*-
"""
大盘复盘模块 — 仅美股宏观指数叙事（A股/港股已移除）。

历史环境变量 MARKET_REVIEW_REGION=cn/both 将被忽略并等同于 us。
"""

import logging
from datetime import datetime
from typing import Optional

from src.config import get_config
from src.notification import NotificationService
from src.market_analyzer import MarketAnalyzer
from src.search_service import SearchService
from src.analyzer import GeminiAnalyzer


logger = logging.getLogger(__name__)


def _normalize_review_region(raw: Optional[str]) -> str:
    r = (raw or "us").strip().lower()
    if r in ("cn", "both", "hk"):
        logger.warning(
            "MARKET_REVIEW_REGION=%s 已不再支持 A股/港股复盘，已按 us 执行。",
            r,
        )
    return "us"


def run_market_review(
    notifier: NotificationService,
    analyzer: Optional[GeminiAnalyzer] = None,
    search_service: Optional[SearchService] = None,
    send_notification: bool = True,
    merge_notification: bool = False,
    override_region: Optional[str] = None,
) -> Optional[str]:
    """
    执行美股大盘复盘分析（指数 + 新闻 + LLM）。

    override_region: 交易日过滤后的有效子集；任何非空值仅用于日志，实际始终走 US 复盘。
    """
    logger.info("开始执行大盘复盘分析（US）...")
    config = get_config()
    cfg_region = getattr(config, "market_review_region", "us") or "us"
    _normalize_review_region(cfg_region)
    if override_region is not None:
        _normalize_review_region(override_region)

    try:
        market_analyzer = MarketAnalyzer(
            search_service=search_service,
            analyzer=analyzer,
            region="us",
        )
        review_report = market_analyzer.run_daily_review()

        if review_report:
            date_str = datetime.now().strftime("%Y%m%d")
            report_filename = f"market_review_{date_str}.md"
            filepath = notifier.save_report_to_file(
                f"# 🎯 大盘复盘\n\n{review_report}",
                report_filename,
            )
            logger.info(f"大盘复盘报告已保存: {filepath}")

            if merge_notification and send_notification:
                logger.info("合并推送模式：跳过大盘复盘单独推送，将在个股+大盘复盘后统一发送")
            elif send_notification and notifier.is_available():
                report_content = f"🎯 大盘复盘\n\n{review_report}"
                success = notifier.send(report_content, email_send_to_all=True)
                if success:
                    logger.info("大盘复盘推送成功")
                else:
                    logger.warning("大盘复盘推送失败")
            elif not send_notification:
                logger.info("已跳过推送通知 (--no-notify)")

            return review_report

    except Exception as e:
        logger.error(f"大盘复盘分析失败: {e}")

    return None
