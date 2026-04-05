# Agent 与传统 Pipeline 能力边界

## 传统 `StockAnalysisPipeline`

- 定时 / CLI / API 同步分析主路径：数据抓取 → 技术/新闻/舆情 → LLM 报告 → 存库与通知。
- 工具集中在 `data_provider`、`SearchService`、`GeminiAnalyzer` 等。

## Agent 路径（`src/agent/`）

- 交互式问股、多步工具调用、会话记忆；能力随技能与工具有增删。
- 与 Pipeline **不保证** 同一组数据源或同一套 Prompt；以本文件 + 实际 `Agent` 工具注册为准。

## 统一方向（长期）

- 共享**数据层**调用（如 capability router、fetcher）减少分叉；
- 在发布说明中标注「仅 Agent」或「仅 Pipeline」的能力，避免用户混淆。
