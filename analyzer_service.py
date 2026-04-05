# -*- coding: utf-8 -*-
"""
===================================
股票智能分析系统 - 分析服务层
===================================

职责：
1. 封装核心分析逻辑，供 CLI、WebUI、Bot 等多入口复用
2. 提供不依赖 ``argparse`` 的程序化 API
3. 支持依赖注入，便于单测与扩展
4. 统一走 ``StockAnalysisPipeline`` 与配置单例
"""

import uuid
from typing import List, Optional

from src.analyzer import AnalysisResult
from src.config import get_config, Config
from src.notification import NotificationService
from src.enums import ReportType
from src.core.pipeline import StockAnalysisPipeline
from src.core.market_review import run_market_review



def analyze_stock(
    stock_code: str,
    config: Config = None,
    full_report: bool = False,
    notifier: Optional[NotificationService] = None
) -> Optional[AnalysisResult]:
    """
    分析单只股票。

    参数:
        stock_code: 标的代码
        config: 配置对象（可选，默认使用单例）
        full_report: 是否生成完整报告
        notifier: 通知服务（可选）

    返回:
        ``AnalysisResult`` 或失败时为 None
    """
    if config is None:
        config = get_config()
    
    # 创建分析流水线
    pipeline = StockAnalysisPipeline(
        config=config,
        query_id=uuid.uuid4().hex,
        query_source="cli"
    )
    
    # 使用通知服务（如果提供）
    if notifier:
        pipeline.notifier = notifier
    
    # 根据full_report参数设置报告类型
    report_type = ReportType.FULL if full_report else ReportType.SIMPLE
    
    # 运行单只股票分析
    result = pipeline.process_single_stock(
        code=stock_code,
        skip_analysis=False,
        single_stock_notify=notifier is not None,
        report_type=report_type
    )
    
    return result

def analyze_stocks(
    stock_codes: List[str],
    config: Config = None,
    full_report: bool = False,
    notifier: Optional[NotificationService] = None
) -> List[AnalysisResult]:
    """
    分析多只标的。

    参数:
        stock_codes: 代码列表
        config: 配置对象（可选，默认单例）
        full_report: 是否完整报告
        notifier: 通知服务（可选）

    返回:
        成功的 ``AnalysisResult`` 列表（无结果的标的不入表）
    """
    if config is None:
        config = get_config()
    
    results = []
    for stock_code in stock_codes:
        result = analyze_stock(stock_code, config, full_report, notifier)
        if result:
            results.append(result)
    
    return results

def perform_market_review(
    config: Config = None,
    notifier: Optional[NotificationService] = None
) -> Optional[str]:
    """
    执行大盘复盘。

    参数:
        config: 配置对象（可选，默认单例）
        notifier: 通知服务（可选，默认用 pipeline 内建）

    返回:
        复盘报告文本，失败时可为 None
    """
    if config is None:
        config = get_config()
    
    # 创建分析流水线以获取analyzer和search_service
    pipeline = StockAnalysisPipeline(
        config=config,
        query_id=uuid.uuid4().hex,
        query_source="cli"
    )
    
    # 使用提供的通知服务或创建新的
    review_notifier = notifier or pipeline.notifier
    
    # 调用大盘复盘函数
    return run_market_review(
        notifier=review_notifier,
        analyzer=pipeline.analyzer,
        search_service=pipeline.search_service
    )


