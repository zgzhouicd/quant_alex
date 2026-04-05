# -*- coding: utf-8 -*-
"""
TechnicalAgent：技术与价格分析专家。

职责包括：
- 拉取实时行情与历史 K 线
- 计算趋势、均线、量能、形态等指标
- 输出结构化的趋势/动能/支撑阻力观点
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from src.agent.agents.base_agent import BaseAgent
from src.agent.protocols import AgentContext, AgentOpinion
from src.agent.runner import try_parse_json

logger = logging.getLogger(__name__)


class TechnicalAgent(BaseAgent):
    agent_name = "technical"
    max_steps = 6
    tool_names = [
        "get_realtime_quote",
        "get_daily_history",
        "analyze_trend",
        "calculate_ma",
        "get_volume_analysis",
        "analyze_pattern",
        "get_chip_distribution",
        "get_derivatives_snapshot",
        "get_analysis_context",
        "get_intraday_signal",
    ]

    def system_prompt(self, ctx: AgentContext) -> str:
        skills = ""
        if self.skill_instructions:
            skills = f"\n## Active Trading Skills\n\n{self.skill_instructions}\n"
        baseline = ""
        if self.technical_skill_policy:
            baseline = f"\n{self.technical_skill_policy}\n"

        return f"""\
You are a **Technical Analysis Agent** specialising in multi-asset trading \
instruments: US equities, futures, and perpetual contracts.

Your task: perform a thorough technical analysis of the given instrument and \
output a structured JSON opinion.

## Workflow (execute stages in order)
1. Fetch realtime quote + daily history (if not already provided)
2. Run trend analysis (MA alignment, MACD, RSI)
3. Analyse volume structure (chip distribution only when available/supported)
4. Identify chart patterns and invalidation levels

{baseline}
{skills}
## Output Format
Return **only** a JSON object (no markdown fences):
{{
  "signal": "strong_buy|buy|hold|sell|strong_sell",
  "confidence": 0.0-1.0,
  "reasoning": "2-3 sentence summary",
  "key_levels": {{
    "support": <float>,
    "resistance": <float>,
    "stop_loss": <float>
  }},
  "trend_score": 0-100,
  "ma_alignment": "bullish|neutral|bearish",
  "volume_status": "heavy|normal|light",
  "pattern": "<detected pattern or none>"
}}
"""

    def build_user_message(self, ctx: AgentContext) -> str:
        parts = [f"Perform technical analysis on instrument **{ctx.stock_code}**"]
        if ctx.stock_name:
            parts[0] += f" ({ctx.stock_name})"
        if ctx.instrument:
            parts.append(f"\n[Instrument]\n{json.dumps(ctx.instrument, ensure_ascii=False, default=str)}")
        if ctx.get_data("session_state"):
            parts.append(f"\n[Session state]\n{json.dumps(ctx.get_data('session_state'), ensure_ascii=False, default=str)}")
        if ctx.get_data("derivatives_snapshot"):
            parts.append(
                f"\n[Existing derivatives snapshot]\n"
                f"{json.dumps(ctx.get_data('derivatives_snapshot'), ensure_ascii=False, default=str)}"
            )
        parts.append("Use your tools to fetch any missing data, then output the JSON opinion.")
        return "\n".join(parts)

    def post_process(self, ctx: AgentContext, raw_text: str) -> Optional[AgentOpinion]:
        """从 LLM 回复中解析 JSON 并构造 :class:`AgentOpinion`。"""
        parsed = try_parse_json(raw_text)
        if parsed is None:
            logger.warning("[TechnicalAgent] failed to parse opinion JSON")
            return None

        return AgentOpinion(
            agent_name=self.agent_name,
            signal=parsed.get("signal", "hold"),
            confidence=float(parsed.get("confidence", 0.5)),
            reasoning=parsed.get("reasoning", ""),
            key_levels={
                k: float(v) for k, v in parsed.get("key_levels", {}).items()
                if isinstance(v, (int, float))
            },
            raw_data=parsed,
        )
