# -*- coding: utf-8 -*-
"""
DecisionAgent：最终综合与决策专家。

职责包括：
- 汇总技术面、情报、风险与各技能 Agent 的观点
- 产出最终「决策仪表盘」JSON
- 生成长/短/中等方向建议，含入场区、止损、目标与杠杆提示
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional

from src.agent.agents.base_agent import BaseAgent
from src.agent.protocols import AgentContext, AgentOpinion, normalize_decision_signal
from src.report_language import normalize_report_language

logger = logging.getLogger(__name__)


class DecisionAgent(BaseAgent):
    """Synthesise prior agent opinions into the final dashboard."""

    agent_name = "decision"
    max_steps = 3  # pure synthesis, should not need many tool calls
    tool_names: Optional[List[str]] = []  # no tool access — works from context only

    @staticmethod
    def _is_chat_mode(ctx: AgentContext) -> bool:
        return ctx.meta.get("response_mode") == "chat"

    def system_prompt(self, ctx: AgentContext) -> str:
        report_language = normalize_report_language(ctx.meta.get("report_language", "zh"))
        if self._is_chat_mode(ctx):
            prompt = """\
You are a **Decision Synthesis Agent** replying directly to the user's latest
stock-analysis question.

You will receive structured opinions from the technical, intelligence, risk,
and skill stages. Synthesize them into a concise, natural-language answer.

Requirements:
- Answer the user's actual question directly
- Use Markdown when helpful
- Keep the response practical and specific
- Highlight the main signal, key reasoning, and major risks
- Do NOT output JSON or code fences unless the user explicitly asks for them
"""
            if report_language == "en":
                return prompt + "\nAlways answer in English.\n"
            return prompt + "\n默认使用中文回答。\n"

        skills = ""
        if self.skill_instructions:
            skills = f"\n## Active Trading Skills\n\n{self.skill_instructions}\n"

        # Read instrument context for asset-class-aware prompt injection
        instrument = ctx.get_data("instrument") or {}
        asset_class = str(instrument.get("asset_class") or "us_equity").strip().lower()
        session_state = ctx.get_data("session_state") or {}
        session_phase = session_state.get("phase", "")
        is_derivatives = asset_class in {"future", "perpetual"}

        asset_context = ""
        if asset_class == "perpetual":
            asset_context = (
                "\n## Asset Context\n"
                "This is a **perpetual contract** (crypto or crypto-derivative).\n"
                "- Apply leverage-aware risk management.\n"
                "- funding_rate and open_interest are key inputs.\n"
                "- Prefer `long` or `short` over `neutral` unless risk is prohibitive.\n"
                "- `leverage_guidance` is required in the output.\n"
            )
        elif asset_class == "future":
            asset_context = (
                "\n## Asset Context\n"
                "This is a **futures contract**.\n"
                "- Account for roll risk and basis when suggesting entry/exit.\n"
                "- `leverage_guidance` is required in the output.\n"
            )
        else:
            asset_context = (
                "\n## Asset Context\n"
                "This is a **US equity** instrument.\n"
            )
        if session_phase:
            asset_context += f"- Current market phase: `{session_phase}`\n"

        prompt = f"""\
You are a **Decision Synthesis Agent** that produces the final directional \
trade Decision Dashboard for multi-asset instruments \
(US equities, futures, perpetual contracts).

You will receive:
1. Structured opinions from a Technical Agent and an Intel Agent
2. Any risk flags raised by a Risk Agent
3. Skill evaluation results (if applicable)
{asset_context}
Your task: synthesise all inputs into a single, actionable Decision Dashboard.
{skills}
## Core Principles
1. **Direction first** — `direction` must be `long | short | neutral`
2. **Precise trade levels** — concrete entry_zone, stop_loss, target_1, target_2
3. **Risk priority** — risk alerts must be prominent; any hard-severity risk forces `neutral`
4. **Checklist visual** — ✅⚠️❌ for each checkpoint
5. **Leverage discipline** — always state leverage_guidance (even if "1x / no leverage")

## Signal Weighting Guidelines
- Technical opinion weight: ~40%
- Intel / sentiment weight: ~30%
- Risk flags weight: ~30% (negative override: any high-severity risk caps at `neutral`)
- If a skill opinion is present, blend it at 20% weight (reducing others proportionally)

## Scoring → Direction mapping
- 80-100: `long` (all conditions met, high conviction)
- 60-79: `long` (mostly positive, minor caveats)
- 40-59: `neutral` (mixed signals, or risk present)
- 20-39: `short` (negative trend + risk)
- 0-19:  `short` (major risk + bearish)

## Output Format
Return a valid JSON object.  The JSON must include at minimum these top-level keys:

```
{{
  "direction": "long|short|neutral",          // PRIMARY — required
  "confidence_level": "high|medium|low",
  "sentiment_score": 0-100,
  "trend_prediction": "...",
  "operation_advice": "...",                   // human-readable, for UI display
  "decision_type": "buy|hold|sell",            // LEGACY compat — derive from direction
  "entry_zone": "price or range string",
  "stop_loss": "price string",
  "target_1": "price string",
  "target_2": "price string (optional)",
  "time_horizon": "intraday|swing|positional",
  "leverage_guidance": "e.g. 1x-2x / avoid leverage",
  "risk_flags": ["list of key risks"],
  "execution_notes": "brief execution note",
  "analysis_summary": "2-3 sentence synthesis",
  "dashboard": {{...}},
  "key_points": ["..."],
  "risk_warning": "..."
}}
```

Rules:
- `direction` is the **primary output**; derive `decision_type` from it:
  `long → buy`, `short → sell`, `neutral → hold`.
- `entry_zone` / `stop_loss` / `target_1` must always be present (use "N/A" if unavailable).
- `leverage_guidance` must always be present.
"""
        if report_language == "en":
            return prompt + """
## Output Language
- Keep every JSON key unchanged.
- Write all human-readable JSON values in English.
"""
        return prompt + """
## 输出语言
- 所有 JSON 键名保持不变。
- 所有面向用户的人类可读文本值必须使用中文。
"""

    def build_user_message(self, ctx: AgentContext) -> str:
        if self._is_chat_mode(ctx):
            parts = [
                "# User Question",
                ctx.query,
                "",
                f"Stock: {ctx.stock_code} ({ctx.stock_name})" if ctx.stock_name else f"Stock: {ctx.stock_code}",
                "",
            ]
        else:
            parts = [
                f"# Synthesis Request for {ctx.stock_code}",
                f"Stock: {ctx.stock_code} ({ctx.stock_name})" if ctx.stock_name else f"Stock: {ctx.stock_code}",
                "",
            ]

        # Feed prior opinions
        if ctx.opinions:
            parts.append("## Agent Opinions")
            for op in ctx.opinions:
                parts.append(f"\n### {op.agent_name}")
                parts.append(f"Signal: {op.signal} | Confidence: {op.confidence:.2f}")
                parts.append(f"Reasoning: {op.reasoning}")
                if op.key_levels:
                    parts.append(f"Key levels: {json.dumps(op.key_levels)}")
                if op.raw_data:
                    extra_keys = {k: v for k, v in op.raw_data.items()
                                  if k not in ("signal", "confidence", "reasoning", "key_levels")}
                    if extra_keys:
                        parts.append(f"Extra data: {json.dumps(extra_keys, ensure_ascii=False, default=str)}")
                parts.append("")

        # Feed risk flags
        if ctx.risk_flags:
            parts.append("## Risk Flags")
            for rf in ctx.risk_flags:
                parts.append(f"- [{rf.get('severity', 'medium')}] {rf.get('category', '')}: {rf.get('description', '')}")
            parts.append("")

        # Skill meta
        requested_skills = ctx.meta.get("skills_requested") or ctx.meta.get("strategies_requested")
        if requested_skills:
            parts.append(f"## Skills: {', '.join(requested_skills)}")
            parts.append("")

        if self._is_chat_mode(ctx):
            parts.append(
                "Answer the user in natural language using the evidence above. "
                "Do not output JSON unless the user explicitly requests structured data."
            )
        else:
            parts.append("Synthesise the above into the Decision Dashboard JSON.")
        return "\n".join(parts)

    def post_process(self, ctx: AgentContext, raw_text: str) -> Optional[AgentOpinion]:
        """Store the parsed dashboard in ctx.meta; also return an opinion."""
        if self._is_chat_mode(ctx):
            text = (raw_text or "").strip()
            if not text:
                return None

            ctx.set_data("final_response_text", text)
            prior = next((op for op in reversed(ctx.opinions) if op.agent_name != self.agent_name), None)
            return AgentOpinion(
                agent_name=self.agent_name,
                signal=prior.signal if prior is not None else "hold",
                confidence=prior.confidence if prior is not None else 0.5,
                reasoning=text,
                raw_data={"response_mode": "chat"},
            )

        from src.agent.runner import parse_dashboard_json
        from src.report_language import (
            infer_decision_type_from_direction,
            infer_direction_from_decision_type,
        )

        dashboard = parse_dashboard_json(raw_text)
        if dashboard:
            # Normalize direction (primary field from new prompt)
            raw_direction = str(dashboard.get("direction") or "").strip().lower()
            if raw_direction in {"long", "short", "neutral"}:
                dashboard["direction"] = raw_direction
                # Derive decision_type from direction for backward compat
                dashboard["decision_type"] = normalize_decision_signal(
                    infer_decision_type_from_direction(raw_direction, default="hold")
                )
            else:
                # Fallback: normalize whatever decision_type the model emitted
                dashboard["decision_type"] = normalize_decision_signal(
                    dashboard.get("decision_type", "hold")
                )
                dashboard["direction"] = infer_direction_from_decision_type(
                    dashboard["decision_type"], default="neutral"
                )

            ctx.set_data("final_dashboard", dashboard)
            try:
                _raw_score = dashboard.get("sentiment_score", 50) or 50
                _score = float(_raw_score)
            except (TypeError, ValueError):
                _score = 50.0
            return AgentOpinion(
                agent_name=self.agent_name,
                signal=dashboard.get("decision_type", "hold"),
                confidence=min(1.0, _score / 100.0),
                reasoning=dashboard.get("analysis_summary", ""),
                raw_data=dashboard,
            )
        else:
            # Even if JSON parsing fails, store the raw text for downstream use
            ctx.set_data("final_dashboard_raw", raw_text)
            logger.warning("[DecisionAgent] failed to parse dashboard JSON")
            return None
