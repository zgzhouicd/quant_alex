# -*- coding: utf-8 -*-
"""
BaseAgent — 所有专职 Agent 的抽象基类。

多 Agent 流水线中的每个 Agent 均继承本类并实现 :meth:`run`。
基类提供：工具子集选择、提示词拼装、经共享 runner 调用 LLM、结构化观点输出等通用能力。
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from src.agent.llm_adapter import LLMToolAdapter
from src.agent.memory import AgentMemory
from src.agent.protocols import AgentContext, AgentOpinion, StageResult, StageStatus
from src.agent.runner import RunLoopResult, run_agent_loop
from src.agent.skills.defaults import extract_skill_id
from src.agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """专职 Agent 的抽象基类。

    子类**必须**实现:
    - :pyattr:`agent_name` — 唯一标识
    - :meth:`system_prompt` — 返回 LLM 系统提示
    - :meth:`build_user_message` — 构造发给 LLM 的用户消息

    子类**可选**覆盖:
    - :pyattr:`tool_names` — 限制可调用工具（None 表示全套）
    - :pyattr:`max_steps` — 单 Agent 最大步数（默认 6）
    - :meth:`post_process` — 将原始 LLM 文本转为 :class:`AgentOpinion`
    """

    # 子类覆盖项
    agent_name: str = "base"
    tool_names: Optional[List[str]] = None  # None → 使用全部工具
    max_steps: int = 6

    def __init__(
        self,
        tool_registry: ToolRegistry,
        llm_adapter: LLMToolAdapter,
        skill_instructions: str = "",
        technical_skill_policy: str = "",
    ):
        self.tool_registry = tool_registry
        self.llm_adapter = llm_adapter
        self.skill_instructions = skill_instructions
        self.technical_skill_policy = technical_skill_policy
        self.memory = AgentMemory.from_config()

    # -----------------------------------------------------------------
    # 抽象接口
    # -----------------------------------------------------------------

    @abstractmethod
    def system_prompt(self, ctx: AgentContext) -> str:
        """构造本 Agent 的系统提示。"""

    @abstractmethod
    def build_user_message(self, ctx: AgentContext) -> str:
        """构造发给 LLM 的用户消息。"""

    # -----------------------------------------------------------------
    # 结构化输出的默认钩子
    # -----------------------------------------------------------------

    def post_process(self, ctx: AgentContext, raw_text: str) -> Optional[AgentOpinion]:
        """从原始 LLM 文本提取 :class:`AgentOpinion`。

        默认返回 ``None``（原文仍保存在 ``StageResult.meta["raw_text"]``）。
        产出分析观点的子类应覆盖本方法。
        """
        return None

    # -----------------------------------------------------------------
    # 执行
    # -----------------------------------------------------------------

    def run(
        self,
        ctx: AgentContext,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        timeout_seconds: Optional[float] = None,
    ) -> StageResult:
        """执行本 Agent，返回 :class:`StageResult`。

        步骤:
        1. 组装 system + user 消息。
        2. 可选注入 ``ctx.data`` 中已预取的数据。
        3. 委托 :func:`run_agent_loop`。
        4. :meth:`post_process` 生成观点。
        5. 将观点追加到 ``ctx.opinions``。
        """
        t0 = time.time()
        result = StageResult(stage_name=self.agent_name, status=StageStatus.RUNNING)

        try:
            messages = self._build_messages(ctx)

            # 若声明了工具子集则限制注册表
            registry = self._filtered_registry()

            loop_result: RunLoopResult = run_agent_loop(
                messages=messages,
                tool_registry=registry,
                llm_adapter=self.llm_adapter,
                max_steps=self.max_steps,
                progress_callback=progress_callback,
                max_wall_clock_seconds=timeout_seconds,
            )

            result.tokens_used = loop_result.total_tokens
            result.tool_calls_count = len(loop_result.tool_calls_log)
            result.meta["raw_text"] = loop_result.content
            result.meta["models_used"] = loop_result.models_used
            result.meta["tool_calls_log"] = loop_result.tool_calls_log

            if not loop_result.success:
                result.status = StageStatus.FAILED
                result.error = loop_result.error or "Agent 循环未产生最终答复"
                return result

            # 后处理为结构化观点
            opinion = self.post_process(ctx, loop_result.content)
            if opinion is not None:
                opinion.agent_name = self.agent_name
                self._apply_memory_calibration(ctx, opinion, result)
                ctx.add_opinion(opinion)
                result.opinion = opinion

            result.status = StageStatus.COMPLETED

        except Exception as exc:
            logger.error("[%s] execution failed: %s", self.agent_name, exc, exc_info=True)
            result.status = StageStatus.FAILED
            result.error = str(exc)
        finally:
            result.duration_s = round(time.time() - t0, 2)

        return result

    # -----------------------------------------------------------------
    # 内部辅助
    # -----------------------------------------------------------------

    def _build_messages(self, ctx: AgentContext) -> List[Dict[str, Any]]:
        """组装发给 LLM 的初始 messages 列表。"""
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt(ctx)},
        ]

        history = ctx.meta.get("conversation_history")
        if isinstance(history, list):
            for message in history:
                if not isinstance(message, dict):
                    continue
                role = message.get("role")
                content = message.get("content")
                if role in {"user", "assistant", "system"} and isinstance(content, str) and content:
                    messages.append({"role": role, "content": content})

        # 将预取数据注入为合成对话，减少重复工具调用
        cached_data = self._inject_cached_data(ctx)
        if cached_data:
            messages.append({"role": "user", "content": cached_data})
            messages.append({"role": "assistant", "content": "已收到预取数据，将继续分析。"})

        messages.append({"role": "user", "content": self.build_user_message(ctx)})
        return messages

    def _inject_cached_data(self, ctx: AgentContext) -> str:
        """根据 ``ctx.data`` 中已有数据构造上下文字符串。

        当前序阶段已拉取本 Agent 所需数据时，可避免再次调用工具。
        """
        import json
        parts: List[str] = []
        for key, value in ctx.data.items():
            if value is not None:
                try:
                    serialised = json.dumps(value, ensure_ascii=False, default=str)
                except (TypeError, ValueError):
                    serialised = str(value)
                # 单字段长度上限，避免撑爆上下文
                if len(serialised) > 8000:
                    serialised = serialised[:8000] + "...(truncated)"
                parts.append(f"[预取: {key}]\n{serialised}")
        memory_context = self._build_memory_context(ctx)
        if memory_context:
            parts.append(memory_context)
        return "\n\n".join(parts) if parts else ""

    def _filtered_registry(self) -> ToolRegistry:
        """返回仅包含 ``self.tool_names`` 的工具注册表。

        ``tool_names`` 为 None 时返回完整注册表。
        """
        if self.tool_names is None:
            return self.tool_registry

        from src.agent.tools.registry import ToolRegistry as TR
        filtered = TR()
        for name in self.tool_names:
            tool_def = self.tool_registry.get(name)
            if tool_def:
                filtered.register(tool_def)
            else:
                logger.warning("[%s] requested tool '%s' not found in registry", self.agent_name, name)
        return filtered

    def _build_memory_context(self, ctx: AgentContext) -> str:
        """摘要近期分析历史，供提示词注入。"""
        if not self.memory.enabled or not ctx.stock_code:
            return ""

        entries = self.memory.get_stock_history(ctx.stock_code, limit=3)
        if not entries:
            return ""

        lines = ["[记忆: 近期分析历史]"]
        for entry in entries:
            parts = [
                entry.date or "未知日期",
                f"signal={entry.signal or 'unknown'}",
                f"sentiment={entry.sentiment_score}",
            ]
            if entry.price_at_analysis:
                parts.append(f"price={entry.price_at_analysis}")
            if entry.outcome_5d is not None:
                parts.append(f"outcome_5d={entry.outcome_5d}")
            if entry.outcome_20d is not None:
                parts.append(f"outcome_20d={entry.outcome_20d}")
            if entry.was_correct is not None:
                parts.append(f"was_correct={entry.was_correct}")
            lines.append("- " + ", ".join(parts))
        lines.append("仅以记忆作为背景参考，勿逐字抄入最终答复。")
        return "\n".join(lines)

    def _apply_memory_calibration(self, ctx: AgentContext, opinion: AgentOpinion, result: StageResult) -> None:
        """在启用时按历史校准调整 confidence。"""
        if not self.memory.enabled:
            return

        skill_id = extract_skill_id(self.agent_name)
        calibration = self.memory.get_calibration(
            agent_name=self.agent_name,
            stock_code=ctx.stock_code or None,
            skill_id=skill_id,
        )
        if not calibration.calibrated:
            return

        raw_confidence = opinion.confidence
        opinion.confidence = max(0.0, min(1.0, raw_confidence * calibration.calibration_factor))
        result.meta["memory_calibration"] = {
            "raw_confidence": raw_confidence,
            "calibrated_confidence": opinion.confidence,
            "factor": calibration.calibration_factor,
            "samples": calibration.total_samples,
        }
