# 时间与存储策略（渐进对齐）

## 原则

- **业务时钟与日历截断**：市场相关「某日」「收盘前后」以各市场时区为准（见 `src/core/trading_calendar.py`）。
- **存储层**：`stock_daily.date` 等为 `Date` 无时区；`DateTime` 列当前多为 **naive local**，与既有 SQLite 实例一致。
- **偏好方向（长期）**：新代码在需要「绝对瞬间」时优先使用 **aware UTC**（`src.utils.timeutil.utc_now`），在展示或 Prompt 中再转换为市场本地或用户语言环境。
- **Docker**：若容器设置 `TZ`，Python naive `datetime.now()` 与系统本地一致；跨时区部署时不要依赖隐式本地。

## 与 P3 路线图

全仓替换 `datetime.now()` 风险高；按模块逐步引入 `utc_now` 与显式 `ZoneInfo`，并同步 regression 测试。
