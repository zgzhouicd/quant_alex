# -*- coding: utf-8 -*-
"""
旧版 ``strategies`` 命名空间的兼容重导出。

提供:
- :class:`StrategyAgent` — :class:`SkillAgent` 的兼容别名
- :class:`StrategyRouter` — :class:`SkillRouter` 的兼容别名
- :class:`StrategyAggregator` — :class:`SkillAggregator` 的兼容别名
"""

from src.agent.strategies.strategy_agent import StrategyAgent
from src.agent.strategies.router import StrategyRouter
from src.agent.strategies.aggregator import StrategyAggregator

__all__ = [
    "StrategyAgent",
    "StrategyRouter",
    "StrategyAggregator",
]
