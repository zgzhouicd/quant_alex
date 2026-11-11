# API v1 与前端调用对照

本页描述 **`/api/v1/*`**（及根路径 **`/api/health`**）与 Web 工作台 `apps/dsa-web/src/api/*.ts` 的对应关系，便于联调与人工测试。

**Web 路由与推送策略**（决策台、notify 默认值等）见 [web-workspace.md](./web-workspace.md)。

**OpenAPI 真源**：启动应用后访问 `/openapi.json`，或使用仓库脚本生成路由列表：

```bash
python scripts/list_openapi_paths.py
python scripts/list_openapi_paths.py --json
```

## 约定

| 列 | 含义 |
|----|------|
| **前端** | 在 `dsa-web` 中封装该路径（或模板路径）的 TS 文件；`—` 表示当前 Web 未封装，仅后端/OpenAPI 可用。 |
| **说明** | 补充产品语义或注意点。 |

路径中的 `{param}` 在 OpenAPI 中为路径参数；前端多为字符串插值。

## 根路径（非 v1）

| Method | Path | Tags | 前端 | 说明 |
|--------|------|------|------|------|
| GET | `/api/health` | Health | — | 负载均衡/探活；与 `/api/v1/health` 语义一致时可任选其一。 |

## Auth

| Method | Path | 前端 | 说明 |
|--------|------|------|------|
| GET | `/api/v1/auth/status` | [auth.ts](../apps/dsa-web/src/api/auth.ts) | |
| POST | `/api/v1/auth/settings` | auth.ts | |
| POST | `/api/v1/auth/login` | auth.ts | |
| POST | `/api/v1/auth/logout` | auth.ts | |
| POST | `/api/v1/auth/change-password` | auth.ts | |

## Health（v1）

| Method | Path | 前端 | 说明 |
|--------|------|------|------|
| GET | `/api/v1/health` | — | 与根 `/api/health` 同属探活；Web 未强制使用。 |

## Agent

| Method | Path | 前端 | 说明 |
|--------|------|------|------|
| GET | `/api/v1/agent/models` | — | 模型发现；可配合设置页自建请求（当前无独立 `agent/models` 封装）。 |
| GET | `/api/v1/agent/skills` | [agent.ts](../apps/dsa-web/src/api/agent.ts) | |
| POST | `/api/v1/agent/chat` | agent.ts | |
| GET | `/api/v1/agent/chat/sessions` | agent.ts | |
| GET | `/api/v1/agent/chat/sessions/{session_id}` | agent.ts | |
| DELETE | `/api/v1/agent/chat/sessions/{session_id}` | agent.ts | |
| POST | `/api/v1/agent/chat/stream` | agent.ts（原生 `fetch`） | SSE/流式。 |
| POST | `/api/v1/agent/research` | — | 深度调研；Web 未封装。 |

## Analysis

| Method | Path | 前端 | 说明 |
|--------|------|------|------|
| POST | `/api/v1/analysis/analyze` | [analysis.ts](../apps/dsa-web/src/api/analysis.ts) | 请求体 `notify` 默认 **false**；Web 不展示外推勾选。 |
| GET | `/api/v1/analysis/status/{task_id}` | analysis.ts | |
| GET | `/api/v1/analysis/tasks` | analysis.ts | |
| GET | `/api/v1/analysis/tasks/stream` | analysis.ts（SSE URL） | EventSource/轮询配合。 |

## History

| Method | Path | 前端 | 说明 |
|--------|------|------|------|
| GET | `/api/v1/history` | [history.ts](../apps/dsa-web/src/api/history.ts) | |
| DELETE | `/api/v1/history` | history.ts | 批量删除。 |
| GET | `/api/v1/history/{record_id}` | history.ts | |
| GET | `/api/v1/history/{record_id}/news` | history.ts | |
| GET | `/api/v1/history/{record_id}/markdown` | history.ts | |

## Stocks

| Method | Path | 前端 | 说明 |
|--------|------|------|------|
| POST | `/api/v1/stocks/extract-from-image` | [stocks.ts](../apps/dsa-web/src/api/stocks.ts) | |
| POST | `/api/v1/stocks/parse-import` | stocks.ts | JSON 或 multipart。 |
| GET | `/api/v1/stocks/{stock_code}/history` | — | K 线历史；Web 若未用则为 —。 |
| GET | `/api/v1/stocks/{stock_code}/quote` | — | 实时报价；Web 若未用则为 —。 |

## Backtest

| Method | Path | 前端 | 说明 |
|--------|------|------|------|
| POST | `/api/v1/backtest/run` | [backtest.ts](../apps/dsa-web/src/api/backtest.ts) | |
| GET | `/api/v1/backtest/results` | backtest.ts | |
| GET | `/api/v1/backtest/performance` | backtest.ts | |
| GET | `/api/v1/backtest/performance/{code}` | backtest.ts | |

## SystemConfig

| Method | Path | 前端 | 说明 |
|--------|------|------|------|
| GET | `/api/v1/system/config` | [systemConfig.ts](../apps/dsa-web/src/api/systemConfig.ts) | |
| PUT | `/api/v1/system/config` | systemConfig.ts | |
| GET | `/api/v1/system/config/schema` | systemConfig.ts | |
| GET | `/api/v1/system/config/export` | systemConfig.ts | |
| POST | `/api/v1/system/config/import` | systemConfig.ts | |
| POST | `/api/v1/system/config/validate` | systemConfig.ts | |
| POST | `/api/v1/system/config/llm/test-channel` | systemConfig.ts | |
| POST | `/api/v1/system/config/llm/discover-models` | systemConfig.ts | |

## Usage

| Method | Path | 前端 | 说明 |
|--------|------|------|------|
| GET | `/api/v1/usage/summary` | — | LLM 用量汇总；Web 未封装。 |

完整路径以 `python scripts/list_openapi_paths.py` 为准。（历史版本曾暴露 `/api/v1/portfolio/*`，已移除。）

## Intraday（路径名保留；默认分钟 `5m`）

| Method | Path | 前端 | 说明 |
|--------|------|------|------|
| GET | `/api/v1/intraday/bars` | — | Web 未封装 |
| POST | `/api/v1/intraday/signal` | — | 单标的分析；Web 用 batch |
| GET | `/api/v1/intraday/signal/latest` | [intraday.ts](../apps/dsa-web/src/api/intraday.ts) | 决策台「读库最新」 |
| POST | `/api/v1/intraday/signals/batch` | intraday.ts | 决策台「扫描信号」 |
| POST | `/api/v1/intraday/scheduler/*` | — | CLI/API；Web 无调度 UI |
| GET | `/api/v1/intraday/scheduler/status` | — | 同上 |

**语义（与 OpenAPI 一致）**：默认 **`interval=5m`**、**`lookback_minutes=390`**；显式 `interval=1d` 时使用 **`lookback_days`**。调度默认 **`intervals: ["5m"]`**、**`poll_seconds=60`**。常量见 `src/core/intraday_defaults.py`。

## PaperTrading

| Method | Path | 前端 | 说明 |
|--------|------|------|------|
| GET/POST | `/api/v1/paper-trading/accounts` | — | Web 未封装；CLI/调度可选 |
| POST | `/api/v1/paper-trading/orders` | — | |
| GET | `/api/v1/paper-trading/orders` | — | |
| GET | `/api/v1/paper-trading/fills` | — | |
| GET | `/api/v1/paper-trading/snapshot/{account_id}` | — | |

## 相关文档

- [architecture-detailed-guide.md](./architecture-detailed-guide.md) — 主链路与入口。
- [CHANGELOG.md](./CHANGELOG.md) — 接口变更记录。
