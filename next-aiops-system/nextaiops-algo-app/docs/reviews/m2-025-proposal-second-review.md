# M2-025 Proposal 二次评审（针对优化稿）

## 评审范围
- `changes/proposed/rolling-experiment-data-layer/proposal.md`
- `changes/proposed/rolling-experiment-data-layer/spec-diff.md`
- `changes/proposed/rolling-experiment-data-layer/tasks.md`

## 总体结论
- **结论：建议通过（Approve with minor follow-ups）**。
- 相比初版，优化稿已实质性补齐此前两个阻塞点：
  1. 时间规范化语义（UTC、秒/毫秒、解析失败）已明确；
  2. `split_train_validate` 的防泄漏边界与 ratio 合法性已明确。
- 同时补充了无原生时间戳数据的 synthetic 适配，显著提升了滚动策略可用性。

## 本轮确认已闭环项

### A. 时间规范化（已闭环）
- 已明确“先转 UTC，再按 UTC date 分区”。
- 已明确数值时间戳秒/毫秒判定规则（`abs(v) >= 1e12`）。
- 已明确解析失败处理路径（默认 fail-fast，支持显式 excluded 模式）。
- 评估：满足复现性要求，跨环境歧义显著降低。

### B. 切分边界语义（已闭环）
- 已明确 `ratio in (0,1)`，非法值抛 `ValueError`。
- 已明确同一 timestamp 不跨 train/validate。
- 已明确 `min(validate.ts) >= max(train.ts)` 作为边界约束。
- 评估：可以有效降低时间泄漏风险。

### C. 无 timestamp 数据适配（已闭环）
- 已引入 `SyntheticTimeConfig`（index + start_time + interval）。
- 已定义启用条件、优先级（真实 timestamp 优先）与 fail-fast 约束。
- 评估：避免 index-only 数据集被一刀切失败，方向正确。

### D. 验收可判定性（基本闭环）
- AC 从“流程命令”升级为“结果断言导向”。
- tasks 增加了单测/集成测覆盖清单，且覆盖核心高风险场景。

## 仍建议在实现前补 3 个小项（非阻塞）

1. **cutoff_day 输入校验再写清一点**
   - 建议在 proposal 或 tasks 补充：`cutoff_day` 非 `YYYY-MM-DD` 时抛 `ValueError`（含错误示例）。

2. **synthetic_interval 语法约束建议显式列举**
   - 建议写明接受格式（如 `Ns/Nmin/Nh`），避免实现时各自解释。

3. **excluded 模式的默认开关命名建议固定**
   - 例如 `on_timestamp_parse_error = "raise" | "exclude"`，减少后续接口讨论成本。

## 最终意见（执行建议）
- 可以进入实现阶段（`rolling_data.py` + 对应测试）。
- 建议先按 `tasks.md` 顺序落地：
  1) 规范化与模型；2) 分区与窗口；3) split 边界；4) synthetic 场景；5) E2E。
- 实现完成后，验收报告应逐条映射 AC，而非仅给 `make test/lint/smoke` 结果。

> 二次评审结论：优化稿质量达到“可实施”标准，建议批准并进入开发。
