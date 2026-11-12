# Image Extract Prompt (Vision LLM)

本文档记录 `src/services/image_stock_extractor.py` 中 `EXTRACT_PROMPT` 的完整内容，便于 PR 审查时评估指令效果。

**当修改 EXTRACT_PROMPT 时**：请同步更新此文件，并在 PR 描述中展示完整变更（before/after），以便审查者评估针对 code+name+confidence 提取的优化程度。

---

## 当前 Prompt（完整）

```
请分析这张股票市场截图或图片，提取其中所有可见的股票代码及名称。

重要：若图中同时显示股票名称和代码（如自选股列表、ETF 列表），必须同时提取两者，每个元素必须包含 code 和 name 字段。

输出格式：仅返回有效的 JSON 数组，不要 markdown、不要解释。
每个元素为对象：{"code":"股票代码","name":"股票名称","confidence":"high|medium|low"}
- code: 必填，美股/美交所 ETF 代码（1–10 位字母与点，如 AAPL、BRK.B、SPY、QQQ）
- name: 若图中有名称则必填（如 Apple、英伟达、SPDR S&P 500），与代码一一对应；仅当图中确实无名称时可省略
- confidence: 必填，识别置信度，high=确定、medium=较确定、low=不确定

示例（图中同时有名称和代码时）：
- 个股：AAPL Apple、NVDA NVIDIA、TSLA Tesla
- ETF：SPY SPDR S&P 500、QQQ Invesco QQQ、VOO Vanguard S&P 500

输出示例：[{"code":"AAPL","name":"Apple","confidence":"high"},{"code":"SPY","name":"SPDR S&P 500 ETF","confidence":"high"}]

禁止只返回代码数组如 ["AAPL","SPY"]，必须使用对象格式。若未找到任何股票代码，返回：[]
```
