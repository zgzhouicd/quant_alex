# 小流量 / 个人使用：运行边界（避免过度优化）

本文是 **默认部署心智模型**：用户量小、单机、优先清晰而非完备架构改造时，以本节为准；与「大规模路线图」冲突时，**以小流量场景为本**。

## 入口怎么选

| 入口 | 适合 | 说明 |
|------|------|------|
| **`python main.py`（CLI）** | 定时/本机批跑 | 产品范围见 `main.py` 文件头：CLI 侧标的与多市场策略与 **Web/API 刻意不同**；多市场分析走 Web 或 API。 |
| **Web / `uvicorn server:app`** | 浏览器工作台、问股、异步分析 | FastAPI + 前端；配置与认证见 README / `docs/full-guide.md`。 |

不要假设「CLI 与 Web 行为完全一致」；需要一致时以 **文档与接口契约** 为准，而不是再抽象一层统一入口（除非已有明确痛点）。

## 数据放哪

- **默认**：SQLite 文件（`DATABASE_PATH`），单机写入足够。
- **`DATABASE_URL`**：仅当确定要上 PostgreSQL 等多后端时再设；小流量 **不必** 为「预留扩展」提前切换。
- 多容器同时写同一 SQLite 文件 **不推荐**；见 [sqlite-multiwrite.md](sqlite-multiwrite.md)。

## 两套「异步任务」边界（真源）

| 组件 | 用途 | 典型触发 |
|------|------|----------|
| **`src/services/task_queue.py` · `AnalysisTaskQueue`** | Web/API 侧分析任务队列、SSE、可选 DB 行 `analysis_async_tasks` | HTTP 触发分析、任务列表/轮询 |
| **`src/services/task_service.py` · `TaskService`** | Bot 等路径下的线程池任务 | IM/机器人侧异步分析 |

两者 **未统一为单一实现**；新功能先对齐已有入口，**不**为「理论整洁」合并队列，除非出现重复实现导致的明确 bug。

## 配置：最小够用

- 至少保证 **LLM** 与一种 **行情/搜索** 相关配置可查 [README](../README.md) 配置表。
- **`DATA_FETCH_MAX_IN_FLIGHT`**：默认 `0`（不限流）；仅当数据源出现封禁/429 再考虑调大限制。
- **`MAX_WORKERS`**：小流量保持较小值通常即可。

## 不建议主动做的事（除非已有症状）

- 大文件拆分（config / search_service / data_provider）仅在为 **修改频繁且痛苦** 时做。
- 全仓时区改造、`session_scope` 全库替换、通知分渠道结构化返回 — **等有运维/产品需求再上**。
- PostgreSQL + 持仓方言改造 — **等确定要弃用单机 SQLite 再上**。

## 相关文档

- [project-architecture-analysis.md](project-architecture-analysis.md) — 问题全景与历史优先级。  
- [timezone-policy.md](timezone-policy.md) — 时间语义演进方向（不必急改）。  
- [agent-capabilities.md](agent-capabilities.md) — Agent 与传统 Pipeline 边界说明。
