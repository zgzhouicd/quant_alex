# -*- coding: utf-8 -*-
"""
RiskAgent：专项风险筛查专家。

职责包括：
- 扫描高管减持、财报预警、监管动作等
- 检查估值异常（PE/PB 极端）
- 评估限售解禁等风险
- 产出可降级或否决其他 Agent 信号的风险标记

风险标记分两档严重程度：
- **soft**：降级信号并展示可见警告
- **hard**：在启用风险覆盖时可直接否决买入类信号
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from src.agent.agents.base_agent import BaseAgent
from src.agent.protocols import AgentContext, AgentOpinion
from src.agent.runner import try_parse_json

logger = logging.getLogger(__name__)


class RiskAgent(BaseAgent):
    agent_name = "risk"
    max_steps = 4
    tool_names = [
        "search_stock_news",
        "get_realtime_quote",
        "get_stock_info",
        "get_derivatives_snapshot",
    ]

    def system_prompt(self, ctx: AgentContext) -> str:
        return """\
You are a **Risk Screening Agent** focused exclusively on identifying \
risks and red flags for the given instrument.

Your task: search for and evaluate ALL potential risk factors, then \
output a structured JSON risk assessment.

## Mandatory Risk Checks (Asset-aware)
For **US equities**, prioritize:
1. Insider / major holder selling
2. Earnings warnings / guidance cuts
3. Regulatory / legal events
4. Industry policy and macro headwinds
5. Lock-up expiration risks
6. Valuation anomalies

For **futures / perpetuals**, prioritize:
1. Funding-rate stress (extreme positive/negative)
2. Open-interest acceleration / crowded positioning
3. Basis dislocation (mark-index spread)
4. Liquidation pressure (or proxy if only proxy is available)
5. Event-driven volatility (exchange maintenance, policy shocks)
6. Technical invalidation levels (support breaks / trend failures)

## Severity Levels
- "high": existential or material risk (lawsuits, fraud, massive insider selling)
- "medium": significant concern (earnings miss, lock-up, sector headwind)
- "low": minor or informational (analyst downgrade, minor insider sale)

## Output Format
Return **only** a JSON object:
{
  "risk_level": "high|medium|low|none",
  "risk_score": 0-100,
  "flags": [
    {
      "category": "insider|earnings|regulatory|industry|lockup|valuation|technical|funding|open_interest|basis|liquidation|event",
      "severity": "high|medium|low",
      "description": "Clear description of the risk",
      "source": "Where this information came from"
    }
  ],
  "veto_buy": true|false,
  "reasoning": "2-3 sentence overall risk assessment",
  "signal_adjustment": "none|downgrade_one|downgrade_two|veto"
}

Important:
- Be thorough but factual.
- Only flag risks backed by evidence from tool results or pre-fetched context.
- If a derivatives snapshot is provided, you must use it as primary evidence \
for derivatives risk checks.
- Do NOT invent risks.
"""

    def build_user_message(self, ctx: AgentContext) -> str:
        parts = [f"Screen stock **{ctx.stock_code}**"]
        if ctx.stock_name:
            parts[0] += f" ({ctx.stock_name})"
        parts.append("for ALL risk factors listed in your instructions.")
        parts.append("Search for latest news if you haven't received intel data yet.")

        if ctx.instrument:
            parts.append(f"\n[Instrument]\n{json.dumps(ctx.instrument, ensure_ascii=False, default=str)}")

        # 注入已有情报数据，避免风险 Agent 重复搜索
        if ctx.get_data("intel_opinion"):
            parts.append(f"\n[Existing intel data]\n{json.dumps(ctx.get_data('intel_opinion'), ensure_ascii=False, default=str)}")
        if ctx.get_data("derivatives_snapshot"):
            parts.append(
                f"\n[Existing derivatives snapshot]\n"
                f"{json.dumps(ctx.get_data('derivatives_snapshot'), ensure_ascii=False, default=str)}"
            )
        if ctx.get_data("session_state"):
            parts.append(
                f"\n[Session state]\n{json.dumps(ctx.get_data('session_state'), ensure_ascii=False, default=str)}"
            )

        return "\n".join(parts)

    def post_process(self, ctx: AgentContext, raw_text: str) -> Optional[AgentOpinion]:
        parsed = try_parse_json(raw_text)
        if parsed is None:
            logger.warning("[RiskAgent] failed to parse risk JSON")
            return None

        # 将结构化风险标记写入上下文
        for flag in parsed.get("flags", []):
            if isinstance(flag, dict):
                ctx.add_risk_flag(
                    category=flag.get("category", "unknown"),
                    description=flag.get("description", ""),
                    severity=flag.get("severity", "medium"),
                )

        return AgentOpinion(
            agent_name=self.agent_name,
            signal=_risk_to_signal(parsed.get("risk_level", "none")),
            confidence=float(parsed.get("risk_score", 50)) / 100.0,
            reasoning=parsed.get("reasoning", ""),
            raw_data=parsed,
        )


def _risk_to_signal(risk_level: str) -> str:
    """将风险等级映射为交易信号（风险越高信号越偏空）。"""
    mapping = {
        "none": "buy",
        "low": "hold",
        "medium": "sell",
        "high": "strong_sell",
    }
    return mapping.get(risk_level, "hold")
