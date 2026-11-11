# -*- coding: utf-8 -*-
from __future__ import annotations

"""
===================================
股票代码与名称映射
===================================

Shared stock code -> name mapping, used by analyzer, data_provider, and name_to_code_resolver.
本产品仅覆盖美股常用标的（MVP 映射）；完整列表请通过索引生成脚本维护。
"""

# Stock code -> name mapping (US equities, MVP)
STOCK_NAME_MAP = {
    "AAPL": "苹果",
    "TSLA": "特斯拉",
    "MSFT": "微软",
    "GOOGL": "谷歌A",
    "GOOG": "谷歌C",
    "AMZN": "亚马逊",
    "NVDA": "英伟达",
    "META": "Meta",
    "AMD": "AMD",
    "INTC": "英特尔",
    "BABA": "阿里巴巴",
    "PDD": "拼多多",
    "JD": "京东",
    "BIDU": "百度",
    "NIO": "蔚来",
    "XPEV": "小鹏汽车",
    "LI": "理想汽车",
    "COIN": "Coinbase",
    "MSTR": "MicroStrategy",
    "JPM": "摩根大通",
    "V": "Visa",
    "MA": "万事达",
    "WMT": "沃尔玛",
    "KO": "可口可乐",
    "PEP": "百事",
    "DIS": "迪士尼",
    "NFLX": "奈飞",
    "ORCL": "甲骨文",
    "CRM": "Salesforce",
    "AVGO": "博通",
    "QCOM": "高通",
    "COST": "好市多",
    "UNH": "联合健康",
    "JNJ": "强生",
    "PG": "宝洁",
    "HD": "家得宝",
    "BAC": "美国银行",
    "XOM": "埃克森美孚",
    "CVX": "雪佛龙",
    "ABBV": "艾伯维",
    "MRK": "默沙东",
    "LLY": "礼来",
    "TSM": "台积电",
    "ASML": "阿斯麦",
    "SPY": "标普500ETF",
    "QQQ": "纳指100ETF",
    "VOO": "Vanguard标普ETF",
    "IVV": "iShares标普ETF",
    "IWM": "罗素2000ETF",
    "DIA": "道指ETF",
}


def is_meaningful_stock_name(name: str | None, stock_code: str) -> bool:
    """Return whether a stock name is useful for display or caching."""
    if not name:
        return False

    normalized_name = str(name).strip()
    if not normalized_name:
        return False

    normalized_code = (stock_code or "").strip().upper()
    if normalized_name.upper() == normalized_code:
        return False

    if normalized_name.startswith("股票"):
        return False

    placeholder_values = {
        "N/A",
        "NA",
        "NONE",
        "NULL",
        "--",
        "-",
        "UNKNOWN",
        "TICKER",
    }
    if normalized_name.upper() in placeholder_values:
        return False

    return True
