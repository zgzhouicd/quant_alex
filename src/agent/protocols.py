# -*- coding: utf-8 -*-
"""
多 Agent 通信共用的协议与数据结构。

为各 Agent、runner、orchestrator 提供基础类型；刻意使用朴素 dataclass（无 ORM），
便于序列化、日志与跨进程传递。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ============================================================
# 枚举
# ============================================================

class Signal(str, Enum):
    """规范化的交易信号标签。"""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


_CANONICAL_DECISION_SIGNAL_MAP: Dict[str, str] = {
    "strong_buy": "buy",
    "buy": "buy",
    "hold": "hold",
    "sell": "sell",
    "strong_sell": "sell",
}


def normalize_decision_signal(signal: Any, default: str = "hold") -> str:
    """将模型侧信号名映射为仪表盘使用的稳定枚举值。"""
    if not isinstance(signal, str):
        return default
    normalized = signal.strip().lower()
    return _CANONICAL_DECISION_SIGNAL_MAP.get(normalized, default)


class StageStatus(str, Enum):
    """流水线单阶段的生命周期状态。"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ============================================================
# AgentContext — 单次分析 run 的共享状态容器
# ============================================================

@dataclass
class AgentContext:
    """单次运行中在各 Agent 之间传递的共享上下文。

    任意 Agent 可读可写；orchestrator 负责填充初始字段并汇总最终结果。
    """

    # --- 标识 ---
    query: str = ""
    stock_code: str = ""
    stock_name: str = ""
    instrument: Dict[str, Any] = field(default_factory=dict)
    session_id: str = ""

    # --- 取数阶段填充的聚合数据 ---
    data: Dict[str, Any] = field(default_factory=dict)
    # 常见键："realtime_quote", "daily_history", "trend_result",
    #        "chip_distribution", "news_context",
    #        "fundamental_context", "derivatives_snapshot", "session_state"

    # --- 各 Agent 输出的观点 ---
    opinions: List["AgentOpinion"] = field(default_factory=list)

    # --- RiskAgent 产生的风险标记 ---
    risk_flags: List[Dict[str, Any]] = field(default_factory=list)

    # --- 任意扩展元数据 ---
    meta: Dict[str, Any] = field(default_factory=dict)
    # 例：{"skills_requested": [...], "user_platform": "feishu"}

    # --- 时间 ---
    created_at: float = field(default_factory=time.time)

    # -----------------------------------------------------------------
    # 便捷方法
    # -----------------------------------------------------------------

    def add_opinion(self, opinion: "AgentOpinion") -> None:
        """追加一条观点；若未写 timestamp 则自动填当前时间。"""
        if opinion.timestamp == 0:
            opinion.timestamp = time.time()
        self.opinions.append(opinion)

    def add_risk_flag(self, category: str, description: str, severity: str = "medium") -> None:
        self.risk_flags.append({
            "category": category,
            "description": description,
            "severity": severity,
            "timestamp": time.time(),
        })

    def get_data(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set_data(self, key: str, value: Any) -> None:
        self.data[key] = value

    @property
    def has_risk_flags(self) -> bool:
        return len(self.risk_flags) > 0


# ============================================================
# AgentOpinion — 单个 Agent 的结构化输出
# ============================================================

@dataclass
class AgentOpinion:
    """某一 Agent 对标的的分析观点。

    参与多 Agent 流水线的每个 Agent 应产出一条 ``AgentOpinion``，追加到 ``AgentContext.opinions``。
    """

    agent_name: str = ""
    signal: str = ""  # 自由文本或 Signal 枚举取值
    confidence: float = 0.0  # 0.0 – 1.0
    reasoning: str = ""
    key_levels: Dict[str, float] = field(default_factory=dict)
    # 例：{"support": 1800.0, "resistance": 1950.0, "stop_loss": 1760.0}
    raw_data: Dict[str, Any] = field(default_factory=dict)
    # Agent 希望向下游传递的额外载荷
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        """将 confidence 限制在 [0.0, 1.0]。"""
        self.confidence = max(0.0, min(1.0, float(self.confidence)))

    @property
    def signal_enum(self) -> Optional[Signal]:
        """尝试把 ``signal`` 解析为 ``Signal``；无法识别则 None。"""
        try:
            return Signal(self.signal)
        except ValueError:
            return None


# ============================================================
# StageResult — 单个流水线阶段的返回类型
# ============================================================

@dataclass
class StageResult:
    """某一阶段（一次 Agent 执行）的结果。

    orchestrator 据此决定继续、重试或中止。
    """

    stage_name: str = ""
    status: StageStatus = StageStatus.PENDING
    opinion: Optional[AgentOpinion] = None
    error: Optional[str] = None
    duration_s: float = 0.0
    tokens_used: int = 0
    tool_calls_count: int = 0
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.status == StageStatus.COMPLETED


# ============================================================
# AgentRunStats — 整次运行的汇总统计
# ============================================================

@dataclass
class AgentRunStats:
    """流水线内所有 Agent 的汇总统计。

    由 orchestrator 收集，用于日志、API 与进度回调展示。
    """

    total_stages: int = 0
    completed_stages: int = 0
    failed_stages: int = 0
    skipped_stages: int = 0
    total_tokens: int = 0
    total_tool_calls: int = 0
    total_duration_s: float = 0.0
    models_used: List[str] = field(default_factory=list)
    stage_results: List[StageResult] = field(default_factory=list)

    def record_stage(self, result: StageResult) -> None:
        """记录阶段结果并更新计数。

        覆盖所有 ``StageStatus``（含 RUNNING/PENDING：计入总数但不归入完成/失败/跳过）。
        """
        self.stage_results.append(result)
        self.total_stages += 1
        self.total_tokens += result.tokens_used
        self.total_tool_calls += result.tool_calls_count
        self.total_duration_s += result.duration_s

        if result.status == StageStatus.COMPLETED:
            self.completed_stages += 1
        elif result.status == StageStatus.FAILED:
            self.failed_stages += 1
        elif result.status == StageStatus.SKIPPED:
            self.skipped_stages += 1
        # RUNNING / PENDING 计入 total_stages，但不计入各子计数器

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_stages": self.total_stages,
            "completed_stages": self.completed_stages,
            "failed_stages": self.failed_stages,
            "skipped_stages": self.skipped_stages,
            "total_tokens": self.total_tokens,
            "total_tool_calls": self.total_tool_calls,
            "total_duration_s": round(self.total_duration_s, 2),
            "models_used": self.models_used,
        }
