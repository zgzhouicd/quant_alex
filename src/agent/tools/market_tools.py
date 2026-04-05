# -*- coding: utf-8 -*-
"""
市场类工具：将 DataFetcherManager 的大盘级能力封装为 Agent 可调用工具。

工具:
- get_market_indices: 主要指数行情
- get_sector_rankings: 板块涨跌幅排行
"""

import logging

from src.agent.tools.registry import ToolParameter, ToolDefinition

logger = logging.getLogger(__name__)


def _get_fetcher_manager():
    """延迟导入，避免循环依赖。"""
    from data_provider import DataFetcherManager
    return DataFetcherManager()


# ============================================================
# get_market_indices
# ============================================================

def _handle_get_market_indices(region: str = "cn") -> dict:
    """获取主要市场指数列表。"""
    manager = _get_fetcher_manager()
    indices = manager.get_main_indices(region=region)

    if not indices:
        return {"error": f"区域 '{region}' 暂无指数数据"}

    return {
        "region": region,
        "indices_count": len(indices),
        "indices": indices,
    }


get_market_indices_tool = ToolDefinition(
    name="get_market_indices",
    description="获取主要市场指数（如 A 股上证/深证/沪深300；美股标普/纳指/道指等），用于大盘概览。",
    parameters=[
        ToolParameter(
            name="region",
            type="string",
            description="市场区域：'cn' A 股，'us' 美股（默认 'cn'）",
            required=False,
            default="cn",
            enum=["cn", "us"],
        ),
    ],
    handler=_handle_get_market_indices,
    category="market",
)


# ============================================================
# get_sector_rankings
# ============================================================

def _handle_get_sector_rankings(top_n: int = 10) -> dict:
    """获取板块涨跌幅排行。"""
    manager = _get_fetcher_manager()
    result = manager.get_sector_rankings(n=top_n)

    if result is None:
        return {"error": "暂无板块排行数据"}

    # get_sector_rankings 返回 Tuple[List[Dict], List[Dict]]，即 (领涨, 领跌)
    if isinstance(result, tuple) and len(result) == 2:
        top_sectors, bottom_sectors = result
        return {
            "top_sectors": top_sectors,
            "bottom_sectors": bottom_sectors,
        }
    elif isinstance(result, list):
        return {"sectors": result}
    else:
        return {"data": str(result)}


get_sector_rankings_tool = ToolDefinition(
    name="get_sector_rankings",
    description="获取行业/板块涨跌幅排行，返回涨幅前 N 与跌幅前 N，辅助板块轮动分析。",
    parameters=[
        ToolParameter(
            name="top_n",
            type="integer",
            description="返回领涨/领跌各多少条（默认 10）",
            required=False,
            default=10,
        ),
    ],
    handler=_handle_get_sector_rankings,
    category="market",
)


ALL_MARKET_TOOLS = [
    get_market_indices_tool,
    get_sector_rankings_tool,
]
