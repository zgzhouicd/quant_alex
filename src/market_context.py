# -*- coding: utf-8 -*-
"""
根据股票代码推断市场语境，供 LLM Prompt 使用。

本产品仅面向美股（及同类美国上市标的），默认注入美股角色与撰写指引。
"""

from typing import Optional


def detect_market(stock_code: Optional[str]) -> str:
    """由代码推断市场：固定返回 ``us``。"""
    return "us"


_MARKET_ROLES = {
    "us": {
        "zh": "美股",
        "en": "US stock",
    },
}

_MARKET_GUIDELINES = {
    "us": {
        "zh": (
            "- 本次分析对象为 **美股**（美国交易所上市股票）。\n"
            "- 美股无涨跌停限制（但有熔断机制），支持 T+0 交易和盘前盘后交易，需关注美元汇率、美联储政策及 SEC 监管动态。"
        ),
        "en": (
            "- This analysis covers a **US stock** (listed on NYSE/NASDAQ).\n"
            "- US stocks have no daily price limits (but have circuit breakers), allow T+0 and pre/after-market trading. Consider USD FX, Fed policy, and SEC regulations."
        ),
    },
}


def get_market_role(stock_code: Optional[str], lang: str = "zh") -> str:
    """返回 LLM Prompt 中使用的市场角色短语。"""
    lang_key = "en" if lang == "en" else "zh"
    return _MARKET_ROLES["us"][lang_key]


def get_market_guidelines(stock_code: Optional[str], lang: str = "zh") -> str:
    """返回该市场下的多行分析指引（注入 Prompt）。"""
    lang_key = "en" if lang == "en" else "zh"
    return _MARKET_GUIDELINES["us"][lang_key]
