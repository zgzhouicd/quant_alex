# Web 工作台说明

本文描述 **当前** `apps/dsa-web` 产品面（路由、推送策略、与 API 的对应关系）。OpenAPI 与逐路径对照见 [api-v1-surface.md](./api-v1-surface.md)。

## 路由

| 路径 | 说明 |
|------|------|
| `/` | 首页：选股分析、历史报告、任务列表；**SSE** `GET /api/v1/analysis/tasks/stream` |
| `/chat` | 问股：多轮 Agent 对话、会话导出 Markdown |
| `/decision` | **决策台**：观察名单、批量日线信号、`/intraday` 会 **302 重定向** 到此 |
| `/backtest` | 回测与次日验证视图 |
| `/settings` | 模型、数据源、认证、智能导入等 |
| `/login` | 开启 Web 认证时使用 |

侧栏顺序：**首页 · 问股 · 决策 · 回测 · 设置**。

## 推送与通知

- **页面内**：分析进度 SSE；决策台右侧「提醒流」（信号或 bar 变更）。
- **外部 IM**（企微、飞书、Telegram 等）：仅在 **`.env` / GitHub Actions Secrets** 中配置；**设置页不展示** `notification` 分类表单。
- **`POST /api/v1/analysis/analyze`**：`notify` 默认 **`false`**；Web 首页无「推送通知」勾选。
- **问股**：无「发送到通知渠道」；已移除 `POST /api/v1/agent/chat/send`。

CLI、定时任务或 API 调用方若需外发，需显式 `notify=true` 且配置通知渠道。

## 日线信号与后端能力边界

- Web 封装：`apps/dsa-web/src/api/intraday.ts` 仅 **`getSignalBatch`**、**`getLatestSignal`**（默认 `interval=1d`）。
- 后端仍提供 `/api/v1/intraday/bars`、`/signal`、调度器、`/api/v1/paper-trading/*` 等；由 **CLI**（`main.py --intraday`）或直接调用 API 使用，**无** Web 模拟盘/调度表单。

## 已移除的 Web 能力（本 fork）

- **`/portfolio` 组合账本** 及 `apps/dsa-web/src/api/portfolio.ts`
- **`IntradayPage`**（原 `/intraday` 分钟+Paper 工作台）
- **设置页通知渠道** 分类（见 `WEB_HIDDEN_SETTINGS_CATEGORIES`）

历史设计说明见 [CHANGELOG.md](./CHANGELOG.md) 与 `full-guide.md` 文末「Portfolio P0」归档节（**API 已删，勿按该节对接 Web**）。

## 构建与静态资源

- 生产：`npm run build` 输出到仓库根目录 `static/`；`python main.py --webui-only` 托管 `static/index.html`。
- 开发：`cd apps/dsa-web && npm run dev`（Vite 5173，`/api` 代理到 8000）。
