# -*- coding: utf-8 -*-
"""
===================================
股票分析命令
===================================

分析指定美股标的，调用 AI 生成分析报告。
"""

import logging
import re
from typing import List, Optional

from bot.commands.base import BotCommand
from bot.models import BotMessage, BotResponse
from data_provider.base import canonical_stock_code
from src.services.instrument_resolver import is_legacy_cn_hk_symbol, resolve_instrument_input

logger = logging.getLogger(__name__)

_US_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


class AnalyzeCommand(BotCommand):
    """
    股票分析命令

    用法：
        /analyze AAPL       - 分析苹果（精简报告）
        /analyze AAPL full  - 分析并生成完整报告
    """

    @property
    def name(self) -> str:
        return "analyze"

    @property
    def aliases(self) -> List[str]:
        return ["a", "分析", "查"]

    @property
    def description(self) -> str:
        return "分析指定美股标的"

    @property
    def usage(self) -> str:
        return "/analyze <股票代码> [full]"

    def validate_args(self, args: List[str]) -> Optional[str]:
        """验证参数"""
        if not args:
            return "请输入股票代码"

        code = canonical_stock_code(args[0])
        if is_legacy_cn_hk_symbol(code):
            return f"无效的股票代码: {code}（本产品仅支持美股等美国上市标的）"
        if not _US_TICKER_RE.fullmatch(code):
            return f"无效的股票代码: {code}（示例: AAPL、MSFT、BRK.B）"

        try:
            resolve_instrument_input(stock_code=code, reject_cn_hk=True)
        except ValueError as exc:
            return str(exc)

        return None

    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:
        """执行分析命令"""
        code = canonical_stock_code(args[0])

        # 检查是否需要完整报告（默认精简，传 full/完整/详细 切换）
        report_type = "simple"
        if len(args) > 1 and args[1].lower() in ["full", "完整", "详细"]:
            report_type = "full"
        logger.info(f"[AnalyzeCommand] 分析股票: {code}, 报告类型: {report_type}")

        try:
            from src.enums import ReportType
            from src.services.task_service import get_task_service

            service = get_task_service()

            result = service.submit_analysis(
                code=code,
                report_type=ReportType.from_str(report_type),
                source_message=message,
            )

            if result.get("success"):
                task_id = result.get("task_id", "")
                return BotResponse.markdown_response(
                    f"✅ **分析任务已提交**\n\n"
                    f"• 股票代码: `{code}`\n"
                    f"• 报告类型: {ReportType.from_str(report_type).display_name}\n"
                    f"• 任务 ID: `{task_id[:20]}...`\n\n"
                    f"分析完成后将自动推送结果。"
                )

            return BotResponse.markdown_response(
                f"❌ **提交失败**: {result.get('message', '未知错误')}"
            )

        except Exception as exc:
            logger.exception("[AnalyzeCommand] 执行失败")
            return BotResponse.markdown_response(f"❌ **分析失败**: {exc}")
