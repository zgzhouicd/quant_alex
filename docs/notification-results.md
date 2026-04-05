# 通知结果结构化（演进说明）

当前各 `send_to_*` 多为 `bool`。若需排障与 UI 分渠道展示，可在集中封装函数中汇总为：

`[{"channel": "feishu", "ok": true}, {"channel": "email", "ok": false, "error": "..."}]`

需保持：**单渠道失败不 raise**，避免拖垮分析主流程；与现有 `NotificationService` 行为一致。
