# -*- coding: utf-8 -*-
"""
IntelAgent：市场情报与舆情聚合专家。

职责包括：
- 检索标的最新新闻、公告与宏观事件
- 识别监管、流动性、财报、资金与清算等风险信号
- 归纳情绪与催化剂（面向美股、期货与永续等）
"""

from __future__ import annotations

import logging
from typing import Optional

from src.agent.agents.base_agent import BaseAgent
from src.agent.protocols import AgentContext, AgentOpinion
from src.agent.runner import try_parse_json

logger = logging.getLogger(__name__)

_ASSET_WORKFLOW = {
    "us_equity": """\
## US Equity Intelligence Workflow
1. Call `search_comprehensive_intel` for latest earnings, analyst upgrades/downgrades,
   institutional activity, regulatory news, macro headwinds, and ETF flow signals.
2. Call `search_stock_news` for breaking news in the past 24-48 hours.
3. Call `get_stock_info` for basic fundamental context (sector, market cap, P/E).

## US Equity Risk Priorities
- Insider / major shareholder sell-downs
- Earnings warnings, guidance cuts, or pre-announcements
- Regulatory actions (SEC, CFTC, DOJ investigations)
- Industry-wide policy or tariff headwinds
- Large lock-up expirations
- Valuation anomalies (extreme P/E, P/S vs sector)
""",
    "perpetual": """\
## Perpetual Contract Intelligence Workflow
1. Call `search_comprehensive_intel` for exchange announcements, regulatory news,
   protocol upgrades, large liquidation events, and ETF/institutional flow.
2. Call `search_stock_news` for breaking on-chain or market structure news.

## Perpetual Risk Priorities
- Exchange operational risks (downtime, halts, fee changes)
- Regulatory crackdowns or ban risks in major jurisdictions
- Protocol vulnerabilities, hacks, or smart contract exploits
- Extreme funding rate environments (prolonged positive or negative)
- Spot ETF approval / rejection catalysts
- Large whale accumulation or distribution signals
""",
    "future": """\
## Futures Intelligence Workflow
1. Call `search_comprehensive_intel` for supply/demand reports, inventory data
   (EIA, USDA, LME), central bank policy, and macro event risk (NFP, CPI, FOMC).
2. Call `search_stock_news` for breaking commodity or macro news.

## Futures Risk Priorities
- Unexpected supply shocks or demand destruction
- Central bank policy pivots affecting rate-linked futures
- Geopolitical disruptions (energy, agriculture, metals)
- Roll / delivery risks near contract expiry
- Basis dislocation or term structure inversion
""",
}


class IntelAgent(BaseAgent):
    agent_name = "intel"
    max_steps = 4
    tool_names = [
        "search_stock_news",
        "search_comprehensive_intel",
        "get_stock_info",
    ]

    def system_prompt(self, ctx: AgentContext) -> str:
        instrument = ctx.get_data("instrument") or {}
        asset_class = str(instrument.get("asset_class") or "us_equity").strip().lower()
        workflow = _ASSET_WORKFLOW.get(asset_class, _ASSET_WORKFLOW["us_equity"])

        return f"""\
You are a **Market Intelligence & Sentiment Agent** covering multi-asset \
instruments: US equities, futures, and perpetual contracts.

Your task: gather the latest news, event catalysts, and risk signals for \
the given instrument, then produce a structured JSON opinion.

{workflow}
## Output Format
Return **only** a valid JSON object:
{{
  "signal": "strong_buy|buy|hold|sell|strong_sell",
  "confidence": 0.0-1.0,
  "reasoning": "2-3 sentence summary covering key news and risk/catalyst balance",
  "risk_alerts": ["list of detected risks"],
  "positive_catalysts": ["list of positive catalysts"],
  "sentiment_label": "very_positive|positive|neutral|negative|very_negative",
  "key_news": [
    {{"title": "...", "impact": "positive|negative|neutral"}}
  ]
}}
"""

    def build_user_message(self, ctx: AgentContext) -> str:
        instrument = ctx.get_data("instrument") or {}
        asset_class = str(instrument.get("asset_class") or "us_equity").strip().lower()

        symbol_label = ctx.stock_name or ctx.stock_code
        parts = [
            f"Gather market intelligence and assess sentiment for **{ctx.stock_code}**"
            + (f" ({ctx.stock_name})" if ctx.stock_name else ""),
            f"Asset class: `{asset_class}`",
            "",
        ]

        if asset_class == "us_equity":
            parts.append(
                "Steps:\n"
                "1. Call `search_comprehensive_intel` for earnings, analyst ratings, "
                "regulatory events, macro outlook, and ETF flows.\n"
                "2. Call `search_stock_news` for breaking news (last 48 h).\n"
                "3. Call `get_stock_info` for sector and fundamental context.\n"
                "4. Output the JSON opinion."
            )
        elif asset_class == "perpetual":
            parts.append(
                "Steps:\n"
                "1. Call `search_comprehensive_intel` for exchange announcements, "
                "regulatory news, on-chain events, and liquidation catalysts.\n"
                "2. Call `search_stock_news` for breaking crypto market news.\n"
                "3. Output the JSON opinion."
            )
        else:  # future
            parts.append(
                "Steps:\n"
                "1. Call `search_comprehensive_intel` for supply/demand reports, "
                "inventory data, macro event risk (FOMC, CPI, NFP), and geopolitical factors.\n"
                "2. Call `search_stock_news` for breaking commodity / macro news.\n"
                "3. Output the JSON opinion."
            )

        return "\n".join(parts)

    def post_process(self, ctx: AgentContext, raw_text: str) -> Optional[AgentOpinion]:
        parsed = try_parse_json(raw_text)
        if parsed is None:
            logger.warning("[IntelAgent] failed to parse opinion JSON")
            return None

        # 缓存情报解析结果，供下游（尤其 RiskAgent）复用，避免重复检索
        ctx.set_data("intel_opinion", parsed)

        # 将风险告警同步到上下文的 risk_flags
        for alert in parsed.get("risk_alerts", []):
            if isinstance(alert, str) and alert:
                ctx.add_risk_flag(category="intel", description=alert)

        return AgentOpinion(
            agent_name=self.agent_name,
            signal=parsed.get("signal", "hold"),
            confidence=float(parsed.get("confidence", 0.5)),
            reasoning=parsed.get("reasoning", ""),
            raw_data=parsed,
        )


