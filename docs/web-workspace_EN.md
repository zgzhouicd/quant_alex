# Web Workspace

Current **dsa-web** product surface: routes, notification policy, and API mapping. See [api-v1-surface.md](./api-v1-surface.md) for HTTP details.

## Routes

| Path | Purpose |
|------|---------|
| `/` | Home: analysis, history, tasks; **SSE** task stream |
| `/chat` | Strategy Q&A; export session as Markdown only |
| `/decision` | **Decision desk**: watchlist, daily (`1d`) batch signals; `/intraday` redirects here |
| `/backtest` | Backtest / next-day validation UI |
| `/settings` | Models, data sources, auth (no notification channel form) |
| `/login` | When web auth is enabled |

Sidebar: **Home · Chat · Decision · Backtest · Settings**.

## Notifications

- **In-browser**: task SSE; decision desk alert stream on signal/bar change.
- **External IM**: optional via `.env` / Actions only; Web settings hide the `notification` category.
- Analysis API: `notify` defaults to **`false`**; no home-page push checkbox.
- Removed: `POST /api/v1/agent/chat/send`.

## Intraday / paper on Web

Web client only calls **batch** and **latest** signal endpoints. Scheduler and paper-trading APIs remain for CLI/API callers, not Web forms.

## Removed from Web (this fork)

- Portfolio ledger UI and `/portfolio`
- Legacy `IntradayPage` (paper + scheduler UI)
- Settings notification category tab

See [CHANGELOG.md](./CHANGELOG.md); `full-guide.md` Portfolio P0 sections are **archived** (APIs removed).
