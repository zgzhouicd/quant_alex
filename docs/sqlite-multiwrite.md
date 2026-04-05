# SQLite 多进程 / 多容器写入

## 现状

单机默认 SQLite 文件库已启用 WAL、`busy_timeout` 与写入重试（见 `DatabaseManager`）。

## 约束

- **多进程同时写同一文件**仍可能产生锁等待或 `database is locked`；水平扩展时优先：
  - 单写入节点 + 只读副本（应用层约束），或
  - 迁移至 PostgreSQL（见 [postgresql.md](postgresql.md)）。
- API **异步任务表** `analysis_async_tasks` 与主分析写路径共享库文件；高并发时观察锁指标再调 `SQLITE_*` 参数或换库。
