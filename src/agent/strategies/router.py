"""兼容旧 import 路径的策略路由封装。"""

from src.agent.skills.router import SkillRouter, StrategyRouter, _DEFAULT_STRATEGIES, _DEFAULT_SKILLS

__all__ = ["SkillRouter", "StrategyRouter", "_DEFAULT_SKILLS", "_DEFAULT_STRATEGIES"]
