# openclaw Skill 集成指南

本文档说明如何通过 [openclaw](https://github.com/openclaw/openclaw) Skill 调用 daily_stock_analysis 的 REST API，实现在 openclaw 对话中触发股票分析的能力。

## 概述

- **集成方式**：openclaw Skill 通过 HTTP 调用 daily_stock_analysis（DSA）REST API
- **适用场景**：已部署 DSA API 服务，希望在 openclaw 对话中触发分析（如「analyze AAPL」「帮我看看 NVDA」）

## 前置条件

1. **daily_stock_analysis 必须已运行**：执行 `python main.py --serve-only` 或通过 Docker 部署，使 API 长期可用
2. **openclaw 需具备 HTTP 调用能力**：如 `system.run` 执行 curl，或内置 HTTP 工具（如 api-tester 等）
3. **说明**：GitHub Actions 仅做定时任务，不长期暴露 API，需本地或 Docker 运行 DSA

## 核心 API 参考

| 接口 | 方法 | 用途 |
|------|------|------|
| `/api/v1/analysis/analyze` | POST | 触发分析（主入口） |
| `/api/v1/analysis/status/{task_id}` | GET | 异步任务状态 |
| `/api/v1/agent/chat` | POST | Agent 策略问股（需 `AGENT_MODE=true`） |
| `/api/health` | GET | 健康检查 |

### 触发分析请求体

```json
{
  "stock_code": "AAPL",
  "report_type": "detailed",
  "force_refresh": true,
  "async_mode": false,
  "notify": false
}
```

- `stock_code`：股票代码（必填）
- `report_type`：`simple` | `detailed` | `brief`
- `force_refresh`：布尔值，是否强制刷新（忽略缓存）
- `async_mode`：布尔值，`false` 时同步返回，`true` 时返回 202 + `task_id` 需轮询

**注意**：`force_refresh`、`async_mode` 为布尔类型，非字符串。

### 响应示例（同步模式）

```json
{
  "query_id": "abc123def456",
  "stock_code": "AAPL",
  "stock_name": "Apple Inc.",
  "report": {
    "summary": {
      "analysis_summary": "...",
      "operation_advice": "持有",
      "trend_prediction": "看多",
      "sentiment_score": 75
    },
    "strategy": {
      "ideal_buy": "210",
      "stop_loss": "195",
      "take_profit": "230"
    }
  },
  "created_at": "2026-03-13T10:00:00"
}
```

## 重要限制与说明

- **美股代码**：Web/API/CLI 仅接受美股、美期货与配置的加密永续；A 股/港股拒收。API 不接受纯中文名，需用户提供 ticker（如 `AAPL`）或由 Skill 解析英文名/简称。
- **同步模式耗时**：`async_mode: false` 时，单次分析约 2–5 分钟，需确保 openclaw 或 HTTP 客户端超时足够
- **异步模式**：`async_mode: true` 返回 202 + `task_id`，需轮询 `GET /api/v1/analysis/status/{task_id}` 直至 `status: completed`

## 股票代码格式

| 类型 | 格式 | 示例 |
|------|------|------|
| 美股 | 字母 ticker | `AAPL`、`TSLA`、`BRK.B` |
| 美期货 | Yahoo 风格 | `ES=F`、`NQ=F` |
| 加密永续 | 交易对 | `BTCUSDT` |
| 美股指数 | SPX / `^` 前缀 | `SPX`、`^GSPC` |
| **不支持** | A 股 / 港股 | 入口层 400 |

## 配置方式

在 `~/.openclaw/openclaw.json` 中配置：

```json
{
  "skills": {
    "entries": {
      "daily-stock-analysis": {
        "enabled": true,
        "env": {
          "DSA_BASE_URL": "http://localhost:8000"
        }
      }
    }
  }
}
```

- 本地部署：`http://localhost:8000` 或 `http://127.0.0.1:8000`
- 远程部署：替换为实际 URL
- **建议**：`DSA_BASE_URL` 勿以 `/` 结尾

## 错误响应格式

| 状态码 | error 字段 | 说明 |
|--------|-------------|------|
| 400 | `validation_error` | 参数错误（如缺少 stock_code） |
| 409 | `duplicate_task` | 该股票正在分析中，拒绝重复提交 |
| 500 | `internal_error` / `analysis_failed` | 分析过程发生错误 |

## 完整 SKILL.md 示例

将以下内容保存到 `~/.openclaw/skills/daily-stock-analysis/SKILL.md`：

```markdown
---
name: daily-stock-analysis
description: 调用 daily_stock_analysis API 进行美股智能分析。当用户询问「analyze AAPL」「分析 NVDA」「帮我看看苹果股票」等时使用。仅支持美股 ticker，A 股/港股拒收。
metadata:
  {"openclaw": {"requires": {"env": ["DSA_BASE_URL"]}, "primaryEnv": "DSA_BASE_URL"}}
---

## 触发条件

当用户请求分析某只美股时（如「analyze AAPL」「分析 NVDA」），使用本 Skill。

## 工作流程

1. **提取 ticker**：识别美股代码（如 AAPL、NVDA、BRK.B）。若用户仅给公司名，可映射常见简称（苹果→AAPL、英伟达→NVDA）；无法映射时提示用户提供 ticker。
2. **调用 API**：向 `{DSA_BASE_URL}/api/v1/analysis/analyze` 发送 POST 请求，请求体：
   ```json
   {"stock_code": "<ticker>", "report_type": "detailed", "force_refresh": true, "async_mode": false, "notify": false}
   ```
3. **等待响应**：同步模式下分析约需 2–5 分钟，请确保 HTTP 客户端超时足够（建议 ≥300 秒）。
4. **解析结果**：从响应的 `report.summary` 中提取 `operation_advice`、`trend_prediction`、`analysis_summary`，从 `report.strategy` 中提取 `ideal_buy`、`stop_loss`、`take_profit`，以简洁格式呈现给用户。
5. **错误处理**：
   - 连接失败：提示检查 DSA 是否运行、DSA_BASE_URL 是否正确
   - 400：检查 stock_code 格式
   - 409：该股票正在分析中，可稍后重试或查询任务状态
   - 500：提示查看 DSA 日志排查

## 股票代码格式

- 美股：AAPL、TSLA、BRK.B
- 美期货：ES=F、NQ=F
- 美股指数：SPX、^GSPC、VIX
- 不支持：A 股六位数字、港股 hk 前缀（API 400）
```

## Agent 策略问股（可选）

若 daily_stock_analysis 已启用 `AGENT_MODE=true`，可调用 Agent 策略问股接口，支持多轮对话与多种策略（缠论、均线金叉等）：

```bash
# 将 {DSA_BASE_URL} 替换为实际配置的 API 地址（如 http://localhost:8000）
curl -X POST {DSA_BASE_URL}/api/v1/agent/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "用均线策略分析 AAPL", "session_id": "optional-session-id"}'
```

响应包含 `content`（分析结论）和 `session_id`（用于多轮对话）。

## 故障排查

| 现象 | 可能原因 | 处理建议 |
|------|----------|----------|
| 连接失败 | DSA 未运行、端口错误、防火墙 | 确认 `python main.py --serve-only` 已启动，检查 `DSA_BASE_URL` |
| 400 错误 | stock_code 格式错误或缺失 | 检查代码格式（见上文表格），确保请求体包含 `stock_code` |
| 500 错误 | AI 配置、数据源、网络问题 | 查看 DSA 日志，确认 GEMINI_API_KEY 等已配置 |
| Agent 400 | Agent 模式未启用 | 在 DSA 的 `.env` 中设置 `AGENT_MODE=true` |
| 分析超时 | 同步模式等待时间过长 | 增加 HTTP 客户端超时，或改用 `async_mode: true` 轮询状态 |

## 认证说明

默认情况下 DSA API 无需认证。若在 `.env` 中启用了 `ADMIN_AUTH_ENABLED=true`，则需在 Skill 调用时携带登录后获得的 Cookie，具体方式取决于 openclaw 的 HTTP 工具能力（当前 API 仅支持 Cookie 认证，不支持 Bearer Token）。
