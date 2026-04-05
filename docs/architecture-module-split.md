# 千行级模块拆分清单（实施顺序建议）

便于按 PR 演进；导入路径应保持稳定（re-export 或兼容 shim）。

| 当前模块 | 约略职责 | 建议子模块（示例） |
|----------|----------|-------------------|
| `src/config.py` | 环境解析、校验、LLM 渠道 | `config/env_loader.py`, `config/llm_channels.py`, `config/data_sources.py`；公开 `Config` / `get_config` 留在包 `__init__` |
| `src/search_service.py` | 多引擎搜索 | `search/providers/`, `search/formatting.py`, `search_service.py` facade |
| `data_provider/base.py` | Fetcher 抽象与管理器 | `base/types.py`, `base/fetcher.py`, `base/manager.py`（`DataFetcherManager` 已与限流等绑定） |

实施时每子 PR 保持 `pytest -m "not network"` 通过，并更新本文件勾选进度。
