# daily_stock_analysis 项目改造方案

## 1. 文档目的

本文档用于指导 `daily_stock_analysis` 从“偏 A 股/港股的股票智能分析系统”改造成“主攻美股、期货、永续合约杠杆方向的 AI 交易分析平台”。

文档重点包括：

- 为什么需要改造
- 改造后的目标系统是什么
- 哪些模块保留，哪些模块移除或降级
- 改造优先级如何排序
- 每个阶段的详细实施计划
- 每个阶段的验收标准
- **当前进度与后续计划**

> **最近更新**: 2026-04-06 — 基于代码审查同步进度、修正分期策略、补充遗留缺口与接下来的执行计划。

---

## 2. 改造背景与目标

### 2.1 当前项目现状

`daily_stock_analysis` 目前已经具备较完整的产品化能力，包括：

- FastAPI API
- WebUI
- Bot 接入
- 通知推送
- 历史记录
- 调度与任务队列
- 多 Agent 分析框架
- 大量测试用例

但其业务能力明显偏向：

- A 股
- 港股
- 股票型分析语义

其核心问题不是“不能支持其他市场”，而是“很多领域假设默认分析对象是股票，且偏向 A/H 股生态”。

### 2.2 新目标

本次改造后，项目目标应明确为：

**一个主攻美股、期货、永续合约方向判断与风险控制的 AI 交易分析平台。**

一期聚焦三类资产：

- `us_equity`
- `future`
- `perpetual`

二期再考虑是否扩展 `crypto_spot`、期权、组合层风控等。

### 2.3 改造原则

本次改造遵循以下原则：

1. 保留产品层能力，不推翻重写
2. 去除 A 股和港股主链路依赖
3. 用“统一交易标的模型”替代“股票代码模型”
4. 用“多资产能力路由”替代“股票数据源切换”
5. 用“方向交易输出”替代“买入/持有/卖出投顾输出”

---

## 3. 总体改造策略

### 3.1 总体路线

采用：

**保留产品外壳，重构交易内核**

保留部分：

- API
- WebUI
- Bot
- 通知系统
- 历史记录
- 调度系统
- Agent 编排框架
- 测试基础设施

重构部分：

- 标的模型
- 数据提供层
- 市场时间与会话逻辑
- Agent 工具体系
- 决策输出模型
- 搜索与情报策略
- 风险分析模块

移除或降级部分：

- A 股与港股主链路
- A/H 股专属数据源主逻辑
- 筹码分布、主力资金流、板块涨跌榜等股票本地市场特化能力

### 3.2 为什么不做“兼容所有市场”

因为当前目标已经非常明确：

- 主攻美股
- 主攻期货
- 主攻永续合约杠杆方向

如果继续保留 A/H 股主链路，代价包括：

- 领域模型复杂度持续上升
- provider 路由更混乱
- prompt 与证据链长期被错误市场语义污染
- 测试矩阵暴涨
- 维护成本失控

因此，应主动聚焦，而不是继续扩散。

---

## 4. 现有模块处理建议

### 4.1 建议保留的模块

以下模块建议保留并继续演进：

- `api/`
- `src/core/pipeline.py`
- `src/agent/orchestrator.py`
- `src/agent/agents/base_agent.py`
- `src/services/`
- `src/repositories/`
- `src/storage.py`
- `src/notification.py`
- `bot/`
- `tests/`

原因：

- 这些模块属于产品能力或基础设施能力
- 重写成本高
- 与市场类型耦合相对较弱

### 4.2 建议重构的模块

以下模块需要重点重构：

- `data_provider/base.py`
- `src/core/trading_calendar.py`
- `src/agent/agents/technical_agent.py`
- `src/agent/agents/intel_agent.py`
- `src/agent/agents/decision_agent.py`
- `src/search_service.py`
- `src/agent/protocols.py`
- `api/v1/schemas/`
- `api/v1/endpoints/analysis.py`

原因：

- 这些模块直接定义了分析对象、数据契约、分析路径和输出结构

### 4.3 建议降级或退出主链路的模块

以下能力建议从主链路移除：

- A 股公告抓取
- 主力资金流
- 筹码分布
- 板块涨跌榜
- 龙虎榜、题材、龙头语义
- A/H 股交易日主逻辑
- AkShare/Tushare/Baostock/Pytdx 主 provider 路由

处理方式建议：

- 不急于删除文件
- 先从主流程中摘除
- 标记 deprecated
- 后续按需彻底移除

---

## 5. 目标系统能力设计

### 5.1 统一标的模型

当前项目默认分析对象是股票代码，这不适合期货与永续。

建议引入统一 instrument 模型，字段建议如下：

- `asset_class`: `us_equity | future | perpetual`
- `symbol`
- `exchange`
- `quote_currency`
- `contract_type`
- `underlying`
- `expiry`
- `is_perpetual`
- `session_mode`

设计目标：

- 美股、期货、永续使用统一入口
- 后续所有 provider 路由、session 判断、agent prompt 都依赖这一层

### 5.2 新的分析输出模型

旧输出偏向股票投顾：

- buy
- hold
- sell

新输出应改为方向交易格式：

- `direction`: `long | short | neutral`
- `confidence`
- `setup_type`
- `entry_zone`
- `stop_loss`
- `target_1`
- `target_2`
- `time_horizon`
- `leverage_guidance`
- `risk_flags`
- `execution_notes`

设计目标：

- 更适合期货与永续
- 美股也可沿用方向交易表达

### 5.3 新的数据能力分层

按“能力”而不是“provider 名称”进行抽象：

- `historical_bars`
- `realtime_quote`
- `instrument_meta`
- `news_feed`
- `fundamentals`
- `macro_events`
- `funding_rate`
- `open_interest`
- `liquidation_data`
- `term_structure`
- `basis_data`
- `volatility_snapshot`

### 5.4 Agent 能力重组

建议保留多 Agent 结构，但重做职责：

- `TechnicalAgent`
- `MarketIntelAgent`
- `DerivativesRiskAgent`
- `MacroRegimeAgent`
- `DecisionAgent`

重点变化：

- 风险 Agent 从一般性风险提示升级为“杠杆/强平/funding/OI/basis 风险判断核心节点”

---

## 6. 改造优先级总览

本项目改造建议分为四个优先级层次：

### P0：架构定向与领域模型重构

必须先做，否则后续全是补丁式开发。

### P1：多资产分析 MVP

目标是先跑通美股与永续主链路，形成可用版本。

### P2：专业交易研究增强

目标是补齐期货、宏观、杠杆风控、执行质量。

### P3：平台化和长期演进

目标是优化前端、历史、回测、运营能力。

---

## 7. 详细改造计划

## P0：架构定向与领域模型重构

### P0-1 统一 instrument schema

#### 目标

用统一交易标的替代 `stock_code`。

#### 修改内容

- 新增 `src/schemas/instrument_schema.py`
- 新增 `src/services/instrument_resolver.py`
- 修改 `src/agent/protocols.py`
- 修改 `src/core/pipeline.py`
- 修改 `data_provider/base.py`

#### 为什么要改

因为：

- 美股还能勉强用股票代码语义
- 期货和永续完全不能
- 如果这一层不统一，后面所有模块都会继续写成“股票系统 + 特例补丁”

#### 交付结果

- 系统内部统一使用 instrument 对象
- pipeline 不再依赖纯 `stock_code`

#### 验收标准

- API 能提交 `asset_class + symbol + exchange`
- pipeline 内部不再强依赖“股票代码就是分析对象”

---

### P0-2 剥离 A/H 股主链路

#### 目标

移除 A 股和港股逻辑对主流程的影响。

#### 修改内容

- 下线 A/H 股作为默认 market 路由
- 将 A/H 股 provider 从主 provider chain 中摘除
- 将 A 股公告、主力资金流、筹码分布从主流程移除

#### 为什么要改

因为项目方向已经明确，不需要继续承担 A/H 股复杂度。

#### 交付结果

- 主流程只面向 `us_equity | future | perpetual`

#### 验收标准

- 新增分析请求时，不再默认解析 A/H 股标的
- A/H 股专属字段不再进入主分析上下文

---

### P0-3 重构 provider routing

#### 目标

从“股票数据源 fallback”改为“按资产与能力路由”。

#### 修改内容

- 新增 capability registry
- 对美股、期货、永续分别定义 provider adapter
- 建立统一调用接口

#### 为什么要改

因为：

- 永续要 funding/OI/liquidation
- 期货要连续合约/term structure
- 美股要 fundamentals/earnings

这些都不是股票 provider fallback 能自然表达的。

#### 交付结果

- provider 不再只是“某个市场数据源”
- 而是“某类资产的某种能力提供者”

#### 验收标准

- 同一 instrument 能根据能力路由到不同 provider
- 系统能区分 `historical_bars` 与 `funding_rate` 这类能力

---

### P0-4 重构交易会话与时间逻辑

#### 目标

支持：

- 美股盘前/盘中/盘后
- 期货日盘/夜盘
- 永续 24/7

#### 修改内容

- 重构 `src/core/trading_calendar.py`
- 新增 session resolver
- 统一“分析截止点”和“最近可用数据时间”的判断

#### 为什么要改

因为时间逻辑是所有实时分析、缓存复用、任务跳过策略的基础。

#### 交付结果

- 多资产统一时间模型

#### 验收标准

- 永续不再被错误判定为“休市”
- 美股可区分盘前和盘后
- 期货可处理夜盘

---

### P0-5 定义新的决策 schema

#### 目标

用方向交易 schema 替代股票投顾 schema。

#### 修改内容

- 修改 `src/agent/agents/decision_agent.py`（**⚠️ 当前未改，prompt 仍为 buy/hold/sell**）
- 修改 `src/schemas/report_schema.py`（✅ 已新增 `direction`）
- 修改 API response schema（✅ 已在响应中输出 `direction`）
- 修改 `src/report_language.py`（✅ 已实现 `infer_direction_from_decision_type` 双向映射）

#### 为什么要改

因为：

- buy/hold/sell 不适合期货和永续
- 需要 entry、stop、target、杠杆建议
- 当前 `direction` 完全靠后处理从 `decision_type` 推断，Agent 本身不产出方向语义

#### 交付结果

- 新增 `direction` 主字段
- **Agent 原生输出 `direction`（而非仅靠后处理推断）**

#### 验收标准

- 决策结果能输出 `long | short | neutral`
- `decision_agent.py` prompt 要求 LLM 直接输出 `direction`
- 同时能给出风险边界与执行建议

---

## P1：多资产分析 MVP

### P1-1 跑通美股分析主链路

#### 目标

先把美股作为一期最稳定资产打通。

#### 修改内容

- 美股行情、K 线、盘前盘后、基本面、新闻打通
- 技术 Agent 和 Intel Agent 优先适配美股

#### 为什么先做美股

因为：

- 最接近现有股票分析结构
- 数据获取和 prompt 迁移成本最低
- 能最快产出业务可见结果

#### 验收标准

- 可输入美股 symbol 进行完整分析
- 输出方向、入场、止损、目标、风险摘要

---

### P1-2 跑通永续合约分析主链路

#### 目标

形成项目差异化核心能力。

#### 修改内容

- 接入 `ccxt` 或交易所原生接口
- 增加 funding rate、OI、basis、liquidation 相关工具
- 风险 Agent 适配永续杠杆场景

#### 为什么优先永续

因为你已明确主攻“永续合约杠杆方向”，这是系统核心定位。

#### 验收标准

- 可分析 BTC/ETH 等主流永续
- 输出 long/short/neutral
- 输出杠杆建议与杠杆风险提示

---

### P1-3 重写 TechnicalAgent

#### 目标

让技术分析从“股票图形分析”升级为“多资产方向分析”。

#### 修改内容

- 动态按资产挂载工具
- 加入波动、结构、资金费率共振判断
- 对期货加入连续合约和 roll-aware 逻辑

#### 验收标准

- 同一 Agent 可识别不同资产类型
- 输出结构不再依赖股票术语

---

### P1-4 重写 IntelAgent

#### 目标

让情报分析与目标资产匹配。

#### 修改内容

- 美股：财报、评级、ETF、宏观
- 永续：交易所公告、监管、资金、流动性事件
- 期货：供需、库存、宏观事件

#### 验收标准

- 情报报告中不再默认出现 A 股公告/主力资金流等旧语义

---

### P1-5 增加衍生品风险能力（方案已调整）

#### 目标

把“杠杆风险”从附属信息提升为主分析节点。

#### 修改内容

- ~~新增 `src/agent/agents/derivatives_risk_agent.py`~~（实际：增强现有 `risk_agent.py`）
- 引入 funding/OI/basis/liquidation 风险分析（✅ 工具与 prompt 已就位）

> **执行偏差**：未新建独立 Agent，改为增强 `RiskAgent`（prompt + 工具 + 快照注入）。RiskAgent 已是独立分析节点，扩展即可覆盖需求，避免 Agent 数量膨胀。

#### 验收标准

- 分析结果中可见明确杠杆风险说明
- 风险 Agent 能单独给出风险等级与否决意见
- 衍生品数据缺失时输出降级提示而非静默跳过

---

## P2：专业交易研究增强

### P2-1 完整支持期货主链路

#### 目标

将期货从“可分析”升级为“专业支持”。

#### 修改内容

- 连续合约
- 主力合约切换
- 期限结构
- 基差
- 宏观日历联动

#### 验收标准

- 至少支持主流指数/商品期货方向分析

---

### P2-2 新增 MacroRegimeAgent

#### 目标

加强美股与期货共用的宏观 regime 判断。

#### 修改内容

- 利率
- CPI/NFP
- DXY
- 流动性
- risk-on / risk-off

#### 为什么要加

因为美股与期货很多方向判断都依赖宏观环境，而不只是个体标的。

#### 验收标准

- 输出结果中包含明确 regime 结论

---

### P2-3 改造搜索策略

#### 目标

从股票新闻搜索变成交易研究搜索。

#### 修改内容

- 美股关键词模板
- 期货宏观/库存模板
- 永续交易所/ETF/funding/liquidation 模板

#### 验收标准

- 搜索结果主题与资产类别匹配

---

### P2-4 回测与历史结果适配方向交易

#### 目标

让历史分析不是只验证涨跌，而是验证方向与风险边界。

#### 修改内容

- 历史记录增加 `direction`、`entry`、`stop`、`targets`
- 回测结果支持 long/short 验证

#### 验收标准

- 系统可以评估方向判断正确性，而不是只看股票次日涨跌

---

## P3：平台化与长期优化

### P3-1 前端全面交易化

#### 目标

让 UI 从“股票分析页”转向“方向交易面板”。

#### 修改内容

- 首页支持 asset_class 输入
- 结果页优先展示方向、入场、止损、目标、杠杆、风险
- 历史页支持按资产类别筛选

#### 验收标准

- 用户在界面层不再感受到股票投顾式语义

---

### P3-2 API 契约稳定化

#### 目标

为后续前端、Bot、外部调用提供稳定接口。

#### 修改内容

- 定义统一 analysis request/response schema
- 为多资产提供版本化 API

#### 验收标准

- API 可稳定承载多资产请求

---

### P3-3 清理遗留 A/H 股代码

#### 目标

在新系统稳定后，彻底清理不再使用的旧逻辑。

#### 修改内容

- 删除已弃用 provider
- 删除旧 prompt
- 删除无效测试
- 清理配置项

#### 验收标准

- 配置、代码、测试不再携带大量废弃市场逻辑

---

## 8. 分阶段时间建议

### 第 1 阶段：P0

~~建议周期：1-2 周~~（已进行中，完成度约 75%，剩余收尾 1-3 天）

目标：

- 确立新领域模型
- 让架构真正转向美股/期货/永续

### 第 2 阶段：P1

建议周期：1-2 周（P0 收尾后开始，部分代码通路已建）

目标：

- 跑通美股 + 永续 MVP
- 可以实际输出方向交易建议

### 第 3 阶段：P2

建议周期：3-6 周

目标：

- 补强期货与宏观能力
- 提升交易研究质量

### 第 4 阶段：P3

建议周期：持续迭代

目标：

- 前端与 API 完整交易化
- 清理技术债

---

## 9. 风险与注意事项

### 9.1 最大风险

最大的风险不是代码实现，而是“旧领域模型残留过多”。

如果继续保留大量：

- 股票默认字段
- A 股默认逻辑
- 股票投顾式输出

那么后续每个新资产支持都会不断返工。

### 9.2 第二大风险

把 provider 当成架构核心，而不是把“资产能力模型”当成架构核心。

正确顺序必须是：

1. 定义资产能力
2. 定义统一契约
3. 再接 provider

### 9.3 第三大风险

没有同步重构测试。

本项目测试基础很好，这反而意味着：

- 只要重构时不同步改测试
- 很快就会出现旧逻辑与新逻辑并存的混乱状态

---

## 10. 最终建议

这个项目后续不应继续被理解为“股票日报系统扩展版”，而应该重新定位为：

**面向美股、期货、永续合约方向交易的研究与决策平台**

最推荐的推进顺序是：

1. 先做 P0，坚定去股票/A 股中心化
2. 再做 P1，优先拿下美股和永续
3. 再做 P2，补齐期货与宏观
4. 最后做 P3，完成产品层清理与升级

只有这样，后续项目结构才会越来越清晰，而不是越来越重。

---

## 11. 执行摘要

### 立即执行的 5 个动作

1. 新增统一 instrument schema
2. 将 A/H 股逻辑从主链路摘除
3. 重写 provider routing 为多资产能力路由
4. 重写 session/calendar 逻辑
5. 将决策输出改为 `long/short/neutral`

### 一期 MVP 目标

- 美股分析完整可用
- 永续分析完整可用
- 输出包含方向、止损、目标、杠杆风险

### 二期增强目标

- 期货完整支持
- 宏观与 regime 支持
- 回测与历史记录适配方向交易

---

## 12. 当前进度追踪（2026-04-06 审查更新）

基于代码审查（`git diff` + 文件扫描），逐条对照各子任务实际完成度。

### P0 进度

| 子任务 | 状态 | 说明 |
|--------|------|------|
| **P0-1** 统一 instrument schema | ✅ 基本完成 | `InstrumentSchema` / `instrument_resolver` 已就位；API 支持 `symbol + asset_class + exchange`；pipeline 双路径运行。**遗留**：`data_provider/base.py` 未修改；pipeline 内部仍以 `code: str` 为主键。 |
| **P0-2** 剥离 A/H 主链路 | 🔶 部分完成 | API 入口 `reject_cn_hk=True` 拦截 A/H 标的；筹码分布按 `asset_class` 条件执行。**遗留**：`DataFetcherManager._init_default_fetchers` 仍注册 A/H 数据源；`pipeline.py` 文件头仍写"A股自选股"；`_attach_belong_boards` 仍有 A 股板块逻辑。 |
| **P0-3** 能力路由 | ✅ 基本完成 | `MarketCapabilityRouter` 实现 5 种能力；pipeline 已集成。**遗留**：底层仍复用 `DataFetcherManager`（P0 过渡合理）。 |
| **P0-4** 交易会话与时间 | ✅ 基本完成 | `SessionState` / `resolve_session_state` / `resolve_effective_date_by_instrument` 三种模式已实现且 pipeline 使用。**遗留**：期货会话是 ET 下近似规则。 |
| **P0-5** 决策 schema | 🔶 部分完成 | `direction` 字段已加入 `report_schema` / `AnalysisResult` / API 响应。**遗留**：`decision_agent.py` 未修改，prompt 仍为 `buy/hold/sell`，方向靠后处理推断。 |

**P0 整体完成度约 75%**。核心路径已建，A/H 清理和 decision prompt 是主要缺口。

### P1 进度

| 子任务 | 状态 | 说明 |
|--------|------|------|
| **P1-1** 美股主链路 | 🔶 代码通路已建 | API → instrument → pipeline → capability_router 全链路串通。**尚未**端到端验证。 |
| **P1-2** 永续主链路 | 🔶 代码通路已建 | `get_derivatives_snapshot` 对接 Binance 公共 API；pipeline 注入衍生品快照。**尚未**端到端验证；仅支持 Binance 风格。 |
| **P1-3** 重写 TechnicalAgent | 🔶 部分完成 | prompt 改为多资产描述；新增衍生品工具。**未做**动态按资产挂载工具。 |
| **P1-4** 重写 IntelAgent | ❌ 未开始 | `intel_agent.py` 未修改，prompt 仍写"A-shares, HK"；工具含 `get_capital_flow`（A 股专属）。 |
| **P1-5** DerivativesRiskAgent | 🔶 方案调整 | 未新建独立 Agent；改为增强 `RiskAgent`（prompt + 工具 + 快照注入）。功能部分达成。 |

**P1 整体完成度约 40%**。IntelAgent 未改、Agent prompt 语义未对齐、端到端未验证。

### P2 / P3 进度

均未启动。

### 已发现的代码级问题

1. **`infer_direction_from_decision_type` 缺少直通**：`value` 为 `long/short/neutral` 时不识别，落入 `default`（`neutral`），`long` 被误判。
2. **`instruments_by_code` 键冲突**：`instrument_to_legacy_code` 仅返回 `symbol`，同 symbol 不同 exchange 时覆盖。
3. **`decision_agent.py` 语义断裂**：prompt 硬编码 `buy/hold/sell`，不输出 `direction`，对期货/永续可能误导 LLM。

---

## 13. 接下来的执行计划

**策略**：先补齐 P0 缺口使架构自洽，再逐项收口 P1 实现 MVP。

### 第一批：P0 收尾（建议 1-3 天）

| 序号 | 任务 | 优先级 | 说明 |
|------|------|--------|------|
| 1 | 修复 `infer_direction_from_decision_type` 直通 | 紧急 | 函数开头增加 `if normalized in {"long","short","neutral"}: return normalized`。一行修复，影响面广。 |
| 2 | 重写 `decision_agent.py` prompt | 高 | 输出 schema 改为 `direction: long/short/neutral`；保留 `decision_type` 兼容但降为辅助。 |
| 3 | 清理 `DataFetcherManager` 默认链中的 A/H 数据源 | 高 | 从 `_init_default_fetchers` 降级/移除 Akshare/Pytdx/Baostock/Efinance。 |
| 4 | 清理 `pipeline.py` 中的 A 股残留 | 中 | 文件头注释改为多资产描述；`_attach_belong_boards` 非 cn market 短路。 |
| 5 | 补全 P0 测试覆盖 | 中 | 目标：新增/改造测试 >= 30 个全部通过。 |

### 第二批：P1 MVP 收口（建议 1-2 周）

| 序号 | 任务 | 优先级 | 说明 |
|------|------|--------|------|
| 6 | 重写 `IntelAgent` prompt 与工具列表 | 高 | 移除 A 股专属描述和 `get_capital_flow`；增加美股/永续/期货情报模板。 |
| 7 | 美股端到端验证 | 高 | 用真实标的（AAPL/TSLA）执行完整分析，验证全链路。 |
| 8 | 永续端到端验证 | 高 | 用 BTCUSDT 验证衍生品快照、风险输出、方向语义。 |
| 9 | TechnicalAgent 按资产动态裁剪工具 | 中 | 按 `asset_class` 过滤不适用工具（如对永续不暴露 `get_chip_distribution`）。 |
| 10 | 确定 P1-5 最终方案 | 中 | 保持"增强 RiskAgent"或拆出独立 Agent，更新文档。 |

### 第三批：P1 门禁检查

| 检查项 | 门禁标准 |
|--------|----------|
| 美股分析成功率 | >= 95%（10 标的 x 3 次） |
| 永续分析成功率 | >= 95%（5 标的 x 3 次） |
| 输出含 `direction` | 100% |
| 输出含 `risk_flags` | 100%（永续/期货路径） |
| P95 耗时 | 美股 <= 25s，永续 <= 20s |
| 回归测试通过率 | 100%（`pytest -m "not network"`） |

---

## 14. 文档使用方式

建议将本文档作为主改造路线图使用：

- 架构讨论时，按优先级章节展开
- 实施时，将每个阶段拆成 issue / milestone
- 开发时，先完成 P0，再进入 P1
- 测试与验收时，按“验收标准”逐项检查

- **进度同步时，更新第 12 节的进度表**

---

## 15. 非目标与边界（Out of Scope）

为避免需求蔓延，本轮改造明确以下非目标：

- 不实现实盘下单与自动交易执行（仅做分析与建议）
- 不在本轮支持 A 股、港股重新接入主链路
- 不在本轮支持期权定价与 Greeks 分析
- 不在本轮构建跨交易所自动对冲与套利执行器
- 不在本轮追求“所有交易所、所有期货品种”全覆盖
- 不在本轮重构整套 Web 视觉风格（仅做功能适配）

边界说明：

- 本轮聚焦“方向判断 + 风险边界 + 杠杆建议”的分析系统
- 输出用于研究与辅助决策，不构成自动执行指令

---

## 16. 迁移与兼容计划（API / 历史数据 / 前端）

### 16.1 API 版本策略

> **实际执行偏差说明（2026-04-06）**：当前实现选择了**在 v1 上渐进扩展**而非新增 v2。`AnalyzeRequest` 新增 `symbol/symbols/asset_class/exchange` 字段并保留旧 `stock_code/stock_codes`；响应中 `direction` 作为新增字段追加，`decision_type` 保留。这种方式降低了前端/Bot 的迁移成本，但需注意文档中关于 v2 的描述不再适用于一期。

- ~~保留现有 `v1` 接口，新增 `v2` 分析接口承载新模型~~（实际：v1 原地扩展）
- `v1` 同时返回 `decision_type`（兼容）和 `direction`（新语义）
- 后续视需要决定是否引入 `v2`；当前 v1 即承载新旧兼容
- 前端 / Bot 可按自身节奏从旧字段迁移到新字段

### 16.2 字段兼容策略

- 新增 `direction`：`long | short | neutral`
- 旧字段 `decision_type` 暂保留 1 个发布周期用于兼容
- 映射规则（临时）：
  - `long -> buy`
  - `neutral -> hold`
  - `short -> sell`

### 16.3 历史数据迁移策略

- 历史记录表新增字段：`asset_class`、`direction`、`entry_zone`、`stop_loss`、`targets`
- 旧记录采用“惰性补全”策略：
  - 查询时如果缺失新字段，返回 `null` 并标记 `schema_version=legacy`
- 新写入统一 `schema_version=v2`

### 16.4 前端兼容策略

- 首页新增 `asset_class` 选择器（默认 `us_equity`）
- 旧报告组件保留读取 `decision_type`
- 新报告组件优先读取 `direction` 与风险边界字段
- 历史页按 `schema_version` 决定渲染模板

### 16.5 下线计划

- 当 `v2` 流量占比 > 90% 且连续 2 周稳定后，开始标记 `v1` 废弃
- `v1` 下线前至少提前 2 个迭代周期公告

---

## 17. KPI 与里程碑门禁（Go / No-Go）

### 17.1 P0 门禁

- `Instrument` 模型接入覆盖核心链路（API -> Pipeline -> Agent）100%
- 新增/改造单元测试 >= 30 个，核心链路通过率 100%
- 不出现将永续误判为休市的回归缺陷（基于回放用例）
- 关键请求失败率（5xx）不高于改造前基线 + 0.5%

未达到以上门禁，不进入 P1。

### 17.2 P1 门禁（MVP 可用）

- 美股与永续主链路成功率 >= 95%（按日统计）
- 单标的分析 P95 耗时：
  - 美股 <= 25s
  - 永续 <= 20s
- 输出结构完整率 >= 98%（`direction/entry/stop/targets/risk_flags`）
- 风险 Agent 触发后，最终建议中风险字段覆盖率 100%

未达到以上门禁，不进入 P2。

### 17.3 P2 门禁（专业增强）

- 期货主链路成功率 >= 93%
- 期货连续合约数据完整率 >= 98%（按交易日）
- 宏观 Regime 输出覆盖率 >= 95%
- 回测可用率 >= 95%（long/short 评估链路可执行）

### 17.4 P3 门禁（平台化）

- `v2` API 流量占比 >= 90%
- 前端新模板覆盖 >= 95% 活跃用户请求
- 已弃用配置项清理率 >= 90%
- 故障恢复演练（降级/熔断）通过率 100%

---

## 18. 数据源与风控运行手册（降级 / 告警 / 熔断）

### 18.1 数据源分层与回退

每类能力定义主源与备源：

- `historical_bars`
  - 主源：按资产配置
  - 备源：同资产备选 provider
- `realtime_quote`
  - 主源：低延迟 provider
  - 备源：聚合行情 provider
- `funding_rate/open_interest/liquidation`
  - 主源：交易所 API
  - 备源：聚合衍生品数据源

回退规则：

1. 主源超时（例如 >3s）触发单次重试
2. 连续失败达到阈值触发备源切换
3. 主备均失败时返回降级结果并打风险标签

### 18.2 告警分级

- P0（紧急）：主链路不可用、连续失败、输出结构缺关键字段
- P1（高）：单能力异常率超过阈值（如 funding/OI 采集失败率 > 10%）
- P2（中）：时延超阈值、缓存命中率异常

建议告警指标：

- 成功率
- P95 耗时
- provider 切换次数
- 空字段率
- 风险 Agent 缺失率

### 18.3 熔断与降级策略

- 数据源熔断：
  - 5 分钟窗口失败率 > 40% 时熔断 10 分钟
- 功能降级：
  - 缺少衍生品数据时，禁止输出高杠杆建议
  - 缺少关键风险字段时，`direction` 只能输出 `neutral`
- 输出安全兜底：
  - 当 `risk_flags` 缺失且数据不完整时，附加 `insufficient_data` 标记

### 18.4 杠杆风控硬约束（建议默认）

- 当出现以下任一条件时，禁止高杠杆建议：
  - funding rate 极端偏离阈值
  - OI 在短时间异常激增
  - 清算密度集中于当前价格邻近区间
  - 关键行情源一致性校验失败
- 默认杠杆建议区间：
  - 正常：1x-3x
  - 中高风险：<=2x
  - 高风险：1x 或观望

---

## 19. 量化验收补充表（按阶段）

### 19.1 P0 量化验收

- 代码层：核心模块重构完成率 >= 90%
- 测试层：新增测试 >= 30，回归通过率 100%
- 稳定性：分析任务异常中断率 <= 2%

### 19.2 P1 量化验收

- 业务层：美股/永续日分析任务成功率 >= 95%
- 质量层：结构化字段完整率 >= 98%
- 性能层：美股 P95 <= 25s，永续 P95 <= 20s

### 19.3 P2 量化验收

- 覆盖层：期货主流品类覆盖达到目标清单 >= 80%
- 研究层：宏观 Regime 输出覆盖 >= 95%
- 评估层：long/short 回测链路可用率 >= 95%

### 19.4 P3 量化验收

- 迁移层：`v2` 使用占比 >= 90%
- 运维层：告警闭环处理 SLA 达标率 >= 95%
- 清理层：遗留 A/H 股主链路代码清理率 >= 90%
