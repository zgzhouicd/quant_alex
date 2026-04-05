# -*- coding: utf-8 -*-
"""
搜索类工具：将 SearchService 封装为 Agent 可调工具。

工具:
- search_stock_news: 检索个股最新新闻
- search_comprehensive_intel: 多维度情报检索
"""

import logging

from src.agent.tools.registry import ToolParameter, ToolDefinition

logger = logging.getLogger(__name__)


def _get_search_service():
    """返回进程内共享的 SearchService 单例。"""
    from src.search_service import get_search_service
    return get_search_service()


def _handle_search_stock_news(stock_code: str, stock_name: str) -> dict:
    """检索与个股相关的最新新闻。"""
    service = _get_search_service()

    if not service.is_available:
        return {"error": "未配置搜索引擎 API，无法搜索"}

    response = service.search_stock_news(stock_code, stock_name, max_results=5)

    if not response.success:
        return {
            "query": response.query,
            "success": False,
            "error": response.error_message,
        }

    return {
        "query": response.query,
        "provider": response.provider,
        "success": True,
        "results_count": len(response.results),
        "results": [
            {
                "title": r.title,
                "snippet": r.snippet,
                "url": r.url,
                "source": r.source,
                "published_date": r.published_date,
            }
            for r in response.results
        ],
    }


search_stock_news_tool = ToolDefinition(
    name="search_stock_news",
    description="按股票代码与名称搜索最新相关新闻，返回标题、摘要、来源与链接。",
    parameters=[
        ToolParameter(
            name="stock_code",
            type="string",
            description="股票代码，如 '600519'",
        ),
        ToolParameter(
            name="stock_name",
            type="string",
            description="股票中文名称，如 '贵州茅台'",
        ),
    ],
    handler=_handle_search_stock_news,
    category="search",
)


# ============================================================
# search_comprehensive_intel
# ============================================================

def _handle_search_comprehensive_intel(stock_code: str, stock_name: str) -> dict:
    """多维度情报聚合搜索。"""
    service = _get_search_service()

    if not service.is_available:
        return {"error": "未配置搜索引擎 API，无法搜索"}

    intel_results = service.search_comprehensive_intel(
        stock_code=stock_code,
        stock_name=stock_name,
        max_searches=6,
    )

    if not intel_results:
        return {"error": "综合情报搜索无结果"}

    # 格式化为可读报告
    report = service.format_intel_report(intel_results, stock_name)

    # 同时返回结构化维度数据
    dimensions = {}
    for dim_name, response in intel_results.items():
        if response and response.success:
            dimensions[dim_name] = {
                "query": response.query,
                "results_count": len(response.results),
                "results": [
                    {
                        "title": r.title,
                        "snippet": r.snippet,
                        "source": r.source,
                    }
                    for r in response.results[:3]  # 每维最多 3 条以省 token
                ],
            }

    return {
        "report": report,
        "dimensions": dimensions,
    }


search_comprehensive_intel_tool = ToolDefinition(
    name="search_comprehensive_intel",
    description="多维度情报：新闻、市场解读、风险、业绩预期、行业趋势等，返回格式化报告与分维度结果。",
    parameters=[
        ToolParameter(
            name="stock_code",
            type="string",
            description="股票代码，如 '600519'",
        ),
        ToolParameter(
            name="stock_name",
            type="string",
            description="股票中文名称，如 '贵州茅台'",
        ),
    ],
    handler=_handle_search_comprehensive_intel,
    category="search",
)


ALL_SEARCH_TOOLS = [
    search_stock_news_tool,
    search_comprehensive_intel_tool,
]
