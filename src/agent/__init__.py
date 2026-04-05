# -*- coding: utf-8 -*-
"""
股票分析系统的 Agent 模块。

提供基于 LLM 的工具调用、可插拔交易策略与多轮对话等能力。
通过环境变量 AGENT_MODE=true 启用。

若只需轻量子模块（如 tools.registry），请使用显式导入，避免拖入 json_repair 等重依赖::

    from src.agent.executor import AgentExecutor, AgentResult
    from src.agent.runner import run_agent_loop, RunLoopResult
    from src.agent.protocols import AgentContext, AgentOpinion, StageResult, AgentRunStats
    from src.agent.orchestrator import AgentOrchestrator
"""


def __getattr__(name):
    """延迟导入：访问包属性时再加载，避免 import json_repair 等副作用。"""
    if name == "AgentExecutor":
        from src.agent.executor import AgentExecutor
        return AgentExecutor
    if name == "AgentResult":
        from src.agent.executor import AgentResult
        return AgentResult
    if name == "RunLoopResult":
        from src.agent.runner import RunLoopResult
        return RunLoopResult
    if name in ("AgentContext", "AgentOpinion", "StageResult", "AgentRunStats"):
        from src.agent import protocols
        return getattr(protocols, name)
    if name == "AgentOrchestrator":
        from src.agent.orchestrator import AgentOrchestrator
        return AgentOrchestrator
    if name == "AgentMemory":
        from src.agent.memory import AgentMemory
        return AgentMemory
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AgentExecutor",
    "AgentResult",
    "RunLoopResult",
    "AgentContext",
    "AgentOpinion",
    "StageResult",
    "AgentRunStats",
    "AgentOrchestrator",
    "AgentMemory",
]
