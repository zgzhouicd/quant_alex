# 项目整体分析报告

<!-- 由架构审阅整理；后续迭代可更新本文件或补充专项文档。 -->

## 目录

1. [整体结构](#一整体结构)
2. [运行流程](#二运行流程)
3. [已确认问题（错漏）](#三已确认问题错漏)
4. [架构可改进点](#四架构可改进点)
5. [改进执行方案](#五改进执行方案)
6. [总结表](#六总结)

---

## 一、整体结构

| 层级 | 路径 | 作用 |
|------|------|------|
| CLI 入口 | `main.py` | 参数解析、定时/单次分析、`--serve`、回测等 |
| API 入口 | `server.py` → `api/app.py` | FastAPI 应用：CORS、静态资源、v1 路由、认证中间件 |
| HTTP 路由 | `api/v1/endpoints/*.py` | 分析任务、历史、日线信号、回测、Agent、系统配置等（**日级组合账本 `/portfolio` 已移除**） |
| 核心编排 | `src/core/pipeline.py` | 单股/批量：拉数 → 技术/搜索/舆情 → LLM → 存库 → 通知 |
| 市场侧 | `src/core/market_review.py`、`market_strategy.py` 等 | 大盘复盘、策略输出 |
| 领域服务 | `src/services/*.py` | 任务队列、分析服务、回测、日内/日线信号、历史、报告渲染等 |
| Agent | `src/agent/` | 问股：编排、工具、策略/技能路由、会话 |
| 数据层 | `data_provider/` | 多数据源适配与降级 |
| 持久化 | `src/storage.py` | SQLite（可配置 URL）、ORM、写重试、业务表 |
| 通知 | `src/notification*.py`、`src/notification_sender/` | 汇总与各渠道发送 |
| 前端 | `apps/dsa-web/` | Web（见 [web-workspace.md](./web-workspace.md)）；`apps/dsa-desktop/` 为 Electron |
| 机器人 | `bot/` | IM 接入 |
| 部署 | `docker/`、`scripts/` | 镜像、Compose、本地脚本 |

**产品定位与实盘边界**：本系统为**辅助交易系统**，不向券商或交易所发送真实委托；用户实盘开仓、平仓、反手在**他端**执行。`paper_trading` 与日内调度中的自动成交仅为**本地模拟**。详见 [架构详解 — 辅助交易与实盘边界](./architecture-detailed-guide.md#辅助交易与实盘边界)。

---

## 二、运行流程

### 1. CLI（`python main.py`）

1. `setup_env()` / `_bootstrap_environment()`：加载 `.env`、可选代理。
2. `parse_arguments()`：仅复盘 / 定时 / 单次 / 回测 / `--serve-only` 等分支。
3. 单次全量：**`run_full_analysis()`**
   - 校验标的（CLI 侧可拒绝 A 股/港股/北交所旧式代码，见 `is_legacy_cn_hk_symbol`）。
   - `_compute_trading_day_filter`：非交易日可整批跳过（除非 `--force-run`）。
   - **`StockAnalysisPipeline`** → **`pipeline.run()`**：线程池并发、可选合并推送。
   - 若开启：`run_market_review()`；合并模式再统一推送。
   - 可选：飞书文档、自动回测。
4. 若 `--serve` / `--serve-only`：**`start_api_server()`**（后台 Uvicorn），再按需驻留。

### 2. API（`uvicorn server:app` 或 `main.py --serve-only`）

1. `api.app.create_app()`：生命周期里挂 `SystemConfigService` 等。
2. **`POST /api/v1/analysis/analyze`**：校验、名称→代码、任务队列去重（进行中 409）、异步执行、SSE 进度（**队列与任务元数据仅进程内**，重启后清空）。
3. Web 静态资源由 FastAPI 托管（生产前需构建前端）。

### 3. Pipeline 内部（`StockAnalysisPipeline`）

**`run()`**：股票列表 → 冻结参考时间 → 可选批量预取行情/名称 → 线程池 **`process_single_stock()`** → 汇总通知/本地报告。单股失败通常记录日志并返回 `None`，不拖垮整批。

---

## 三、已确认问题（错漏）

按严重程度排序（与代码位置对应，便于检索修复）。

### 严重——可观测性 / 自动化可靠性

#### P1. `run_full_analysis` 吞异常，CLI 失败仍可能退出码 0

`main.py` 中 `run_full_analysis` 最外层 `except Exception` 只打日志、不 `re-raise`、不返回失败状态；`main()` 正常路径分支仍 **`return 0`**。Cron / CI / 容器健康逻辑无法凭退出码判断分析是否成功。

**建议修复：** `run_full_analysis` 返回 `bool` 或重新抛出；`main()` 据结果 `return 1`。

**状态：** 已落地（见阶段一表）；`run_full_analysis` 返回成功与否，`main()` 在常规单次分析路径可依失败返回退出码 `1`。

#### P2. `has_today_data` 按自然日判断，周末/节假日断点续传易失效

`src/storage.py` 内已注释：目标日期为**自然日**而非最新交易日，休市日运行即使用户库中已有「最后交易日」数据也可能判为无数据，导致重复拉取。

**建议修复：** 断点续传与「最新可复用交易日」对齐（结合 `trading_calendar`）。

**状态：** 省略 `target_date` 的 `has_today_data` 已按 `get_market_for_stock` + `get_effective_trading_date` 解析检查日；显式传入日期的语义未改。

#### P3. 大量 `datetime.now()` 无时区与时区混用

部分路径用 UTC（如 `resume_reference_time`、搜索层），ORM 与业务多处用本地 `datetime.now()`。Docker 设 `TZ=Asia/Shanghai` 时表现可一致，但跨环境或多时区时，**时间窗口类逻辑**（历史查询、cutoff、`has_today_data`）易出现边界错误。

**建议修复：** 存储统一 UTC，展示层再转本地。

**状态：** 已补充 `docs/timezone-policy.md` 与 `src/utils/timeutil.utc_now`；全仓 `datetime.now` 替换仍分批进行。

---

### 中等——逻辑或稳定性

#### P4. 任务队列为进程内单例，重启后内存任务状态丢失

`AnalysisTaskQueue` 状态在内存；进程重启后进行中任务与去重状态不一致，前端易见异常或孤儿任务。

**建议：** 任务状态落库或启动时清理/恢复策略。

**状态：** `analysis_async_tasks` 表持久化任务快照；进程启动 reconcile 将未完成任务标为 `failed`；`get_task` 可从 DB hydrate。内存队列与 SSE 仍为进程内。

#### P5. `analysis_delay` 在主线程收集循环 `sleep`，对线程池并发峰值几乎无效

`src/core/pipeline.py` 内已有注释说明：不约束 `ThreadPoolExecutor` 内同时发起的请求。若目的是「限流」，需在数据层或 fetcher 层做 semaphore/令牌桶。

**状态：** `DataFetcherManager.get_daily_data` 可选 `DATA_FETCH_MAX_IN_FLIGHT`（`>0` 时限流同时在飞），默认 `0` 不改变现网行为。

#### P6. API 路径下每次分析新建完整 `StockAnalysisPipeline`

`AnalysisService.analyze_stock` 每次 `StockAnalysisPipeline(...)`，初始化包含 DB、FetcherManager、Analyzer、SearchService 等，**高并发时开销大**。

**建议：** 共享重型依赖或对象池。

**状态：** `AnalysisService.analyze_stock` 对 `isinstance(config, Config)` 使用进程内 `PipelineSharedRuntime`；每请求仍新建 `StockAnalysisPipeline`，但复用其重子系统。

#### P7. `get_session()` 与 `session_scope()` 混用，事务语义不统一

`get_session()` 返回裸 Session；大量 `with get_session()` 依赖 SQLAlchemy 会话上下文行为，与显式 `session_scope()` 的 rollback 语义易混淆，长期易引入泄漏或未提交事务。

**建议：** 对外统一推荐 `session_scope()`，逐步收敛 API。

**状态：** 返回 ORM 实体并在会话外继续使用的路径（如 `storage` 读表、`backtest_repo`、`stock_repo`）仍用 `get_session` + 显式 `commit`，避免 `session_scope` 关闭后出现 DetachedInstanceError；`session_scope` 仍推荐用于纯服务内短事务。异步任务写库在 `storage` 内显式 `commit`。

#### P8. `_find_sniper_in_dashboard` 嵌套深度硬编码

`sniper_points` 结构略变即可能提取失败，回测/历史价位静默为空。

**建议：** 递归或更强 schema 约束 LLM 输出。

#### P9. Docker Compose 内存上限 512M 可能偏紧

`docker/docker-compose.yml` 中 `deploy.resources.limits.memory: 512M` 对 Python + LLM + Pandas + 多数据源偏紧，易 OOM 重启。

**建议：** 提高至 1G 或文档注明按环境调整。

---

### 轻度——质量与可维护性

#### P10. `test_env.py` 用 `return` 代替 `assert`

触发 `PytestReturnNotNoneWarning`，且失败路径不一定使 pytest 失败。

#### P11. Schema 类名 `TestLLMChannelRequest` 被 pytest 当作测试类收集

触发 `PytestCollectionWarning`，建议改名（不以 `Test` 为前缀的 Pydantic 模型名）。

#### P12. 仓库缺少根目录 `.gitignore` 时易跟踪 `.pyc`、`__pycache__`、大体积素材

clone 体积与噪音大；应在仓库根配置忽略规则。

#### P13. `main.py` 顶部说明与 README 多市场叙述不一致

CLI 与 Web/API 支持范围不同，需在文档或文件头对齐说明，避免误导。

---

## 四、架构可改进点

| 项 | 说明 |
|----|------|
| **A. `config.py` 过大** | 配置读取、校验、LLM 多渠道等集中在一个大类；可拆子配置模块，`config_registry` 已承担 UI 元数据，业务侧可进一步分域。 |
| **B. `search_service.py` 过大** | 单文件维护成本高；可按 provider / 引擎 / 格式化拆分。 |
| **C. `data_provider/base.py` 过大** | 抽象、管理器、标准化等可拆文件，边界更清晰。 |
| **D. SQLite 多进程写入** | 已有 WAL、`BEGIN IMMEDIATE`、重试；水平扩展或多容器写仍需文档约束或迁移 PostgreSQL。 |
| **E. Pipeline 与 AnalysisService 双层** | API → TaskQueue → AnalysisService → Pipeline，中间层偏薄时可合并或共享实例，降低栈深与重复初始化。 |
| **F. 单例 + 测试 ` _instance = None`** | 测试脆弱；长期可向依赖注入或 fixture 管理收敛。 |
| **G. 通知失败粒度** | 多渠道时仅整体成功/失败，可返回分渠道结果便于排障与 UI。 |
| **H. Agent 与传统路径分叉** | `pipeline` 内两条分析路径并行演进，易出现能力不一致；可统一工具层或明确能力矩阵。 |

---

## 五、改进执行方案

### 阶段一：缺陷修复（小改动、高收益）

| # | 问题 | 涉及 | 动作 | 状态 |
|---|------|------|------|------|
| 1 | P1 退出码 | `main.py` | `run_full_analysis` 返回 `bool`；`main()` 失败时退出码 `1` | 已落地 |
| 2 | P10 测试 | `test_env.py` | `test_config` 使用 `assert`；外网用例标 `network` + `skip`/`fail` | 已落地 |
| 3 | P11 命名 | `api` + `apps/dsa-web` | `LLMChannelProbeRequest` / `LLMChannelProbeResponse` | 已落地 |
| 4 | P12 忽略规则 | 根目录 `.gitignore` | Python/venv/日志等 | 已落地 |
| 5 | P9 内存 | `docker/docker-compose.yml` | 默认 `1024M` | 已落地 |

另：阶段二 **P8**（`_find_sniper_in_dashboard` 递归）已在存储层落地；**P13** 已更新 `main.py` 文件头说明。

### 阶段二：稳定性（中等工作量）

| # | 问题 | 动作 | 状态 |
|---|------|------|------|
| 1 | P2 断点续传 | 与最新交易日对齐的 `has_*` 或新 API | 已落地（无参 `has_today_data` 按有效交易日） |
| 2 | P3 时区 | 存储 UTC、展示本地化 | 部分（政策文档 + `utc_now`；全仓替换待续） |
| 3 | P6 Pipeline | 共享重型依赖或每 worker 单例 | 已落地（`PipelineSharedRuntime` + API 路径） |
| 4 | P7 Session | 统一 `session_scope` 用法 | 部分（文档与短时事务推荐；返回 ORM 的仓库仍以 `get_session` 为主） |
| 5 | P8 sniper | 递归提取或 schema 强约束 | 已落地（递归提取） |

### 阶段三：架构迭代（按需、可分 PR）

- 拆分 `config.py` / `search_service.py` / `data_provider/base.py`（逐项、可测）。**小流量默认可不做**，见 `docs/small-scale-operations.md`。
- API 异步任务：**`analysis_async_tasks` + `AnalysisTaskQueue` 持久化/ reconcile 已落地**；Bot 侧 `TaskService` 仍为独立路径。
- 通知结果结构化返回。
- 测试隔离与 DI 演进。

### 阶段四：长期

- PostgreSQL 迁移路径（连接串与 SQL 方言差异）。**仅多实例/合规需求时优先考虑**。
- Agent 与传统路径的统一或文档化边界（`docs/agent-capabilities.md` 已提供文档边界；代码统一非必须）。
- 外部 HTTP 层 mock，补强离线测试。

**小流量默认策略**：避免为架构图而重构；以 `docs/small-scale-operations.md` 为入口边界真源。

---

## 六、总结

| 层面 | 结论 |
|------|------|
| **整体** | 主链路完整；离线测试规模大；多源降级与 fail-open 设计较成熟。 |
| **最紧迫** | 时区一致性（P3）、断点续传边缘语义（P2 显式日期）、会话与事务统一（P7）影响自动化与数据可信度。（P1、无参 P2、P6 轻量优化已阶段性落地，见各条 **状态**。） |
| **中期** | 任务跨进程可见性（P4 持久化进展）、并发限流（P5）、高并发 API 体验（P6 共享运行时）。 |
| **维护** | 若干「千行级」模块适合分阶段拆分，不必一次性大重构。 |

---

## 参考与验证

- **流程图与主链路扩容导读**：[architecture-detailed-guide.md](./architecture-detailed-guide.md)（CLI / API 队列 / Pipeline 双路径 / Agent 编排）。
- 仓库惯例验证：`./scripts/ci_gate.sh`、`uv run python -m pytest -m "not network"`。
- 极小用户量/Lab 部署的优先级与禁做项：**[小流量运行边界](small-scale-operations.md)**。
- 本文问题列表来自代码审阅与静态阅读；修复后应在对应模块补充测试并更新 `docs/CHANGELOG.md` 的 `[Unreleased]`（若对外行为或运维可见）。
