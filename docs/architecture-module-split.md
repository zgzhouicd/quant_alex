# 千行级模块拆分清单（实施顺序建议）

便于按 PR 演进；导入路径应保持稳定（re-export 或兼容 shim）。

| 当前模块 | 约略职责 | 建议子模块（示例） |
|----------|----------|-------------------|
| `src/config.py` | 环境解析、校验、LLM 渠道 | **进行中**：`src/config_parsers.py`、`src/config_llm_channels.py` 已拆出；`Config` / `get_config` 仍留在 `config.py` |
| `src/search_service.py` | 多引擎搜索 | **进行中**：`search_models` / `search_http` / `search_base` 已拆出；后续 `search/providers/` + facade |
| `data_provider/base.py` | Fetcher 抽象与管理器 | **进行中**：`base_fetcher.py`、`fetcher_manager.py`、`errors.py`、`symbol_normalize.py`；`base.py` 为兼容 re-export |

实施时每子 PR 保持 `pytest -m "not network"` 通过，并更新本文件勾选进度。
