# PostgreSQL（可选后端）

## 连接

设置环境变量 **`DATABASE_URL`** 为 SQLAlchemy URL，例如：

`postgresql+psycopg://user:pass@host:5432/dbname`

未设置时仍使用 `DATABASE_PATH` 对应的 SQLite 文件（默认行为不变）。

## 注意

- 历史版本的日级 **Portfolio 账本** API 已移除；若在 PostgreSQL 上扩展新的串行写路径，应单独设计事务边界（勿再引用已删除的 `portfolio_write_session`）。
- 新建表随 `Base.metadata.create_all` 创建；生产环境建议后续引入迁移工具（当前仓库无 Alembic）。
- JSON 与文本字段行为与 SQLite 略有差异，任务表 `result_json` 等为 `Text` 存储的 JSON 字符串，两方言均可使用。
