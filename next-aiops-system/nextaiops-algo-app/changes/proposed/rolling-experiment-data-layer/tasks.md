# Tasks - Proposal ID: M2-025

## Implementation Checklist

| # | Task | Module | Status | Notes |
|---|------|--------|--------|-------|
| 1 | 新增 `PartitionStatus` + `ExclusionReason` + `DayPartition` + `SyntheticTimeConfig` | pipeline/rolling_data.py | done | pydantic BaseModel |
| 2 | 实现 timestamp 规范化（UTC、秒/毫秒识别、解析失败策略） | pipeline/rolling_data.py | done | fail-fast + 可选 excluded 模式 |
| 3 | 实现 `build_day_partitions`（含 synthetic timestamp 适配） | pipeline/rolling_data.py | done | 无 timestamp 时支持 index+start+interval |
| 4 | 实现 `partition_tables` | pipeline/rolling_data.py | done | 仅返回 valid 分区 |
| 5 | 实现 `cumulative_training_window` | pipeline/rolling_data.py | done | 合并 <= cutoff_day 分区 |
| 6 | 实现 `split_train_validate` 边界保护 | pipeline/rolling_data.py | done | `ratio in (0,1)` + 同 ts 不跨集合 |
| 7 | 单元测试：UTC 分区一致性 + 秒毫秒识别 + 解析失败 | tests/unit/test_rolling_data.py | done | 真实/数值/非法 timestamp |
| 8 | 单元测试：synthetic timestamp（正常/缺参/非法 interval/非单调 index） | tests/unit/test_rolling_data.py | done | 可复现断言 |
| 9 | 单元测试：split 边界（非法 ratio、同 ts 不跨集合、最小样本） | tests/unit/test_rolling_data.py | done | 泄漏防护 |
| 10 | 集成测试：多天 CSV → 分区 → 窗口 → 切分（含 synthetic 场景） | tests/integration/test_rolling_data_e2e.py | done | 端到端数据流 |

## Verification Steps
1. Run `make test` → 新增测试与既有 pipeline 相关测试均通过
2. Run `make lint` → 无 lint/type 错误
3. Run `make smoke` → 无回归（用于回归检查，不作为本提案核心验收）
4. 关键结果断言（必须提供测试报告）：
   - UTC 归一后分区数量/日期顺序/状态与预期一致
   - `cumulative_training_window` 在给定 cutoff 下范围与行数可判定
   - `split_train_validate` 满足 `min(validate.ts) >= max(train.ts)` 且同 timestamp 不跨集合
   - synthetic 模式同输入重复运行结果一致

## Rollback Plan
- 删除 `pipeline/rolling_data.py` 与对应测试文件
- 无既有代码被修改，回滚零风险

## Dependencies
- **Blocked by**: 无
- **Blocks**: M2-026（滚动实验引擎）


## Implementation Notes（来自二次评审，放入实现阶段）
- `cutoff_day` 输入校验：非 `YYYY-MM-DD` 时抛 `ValueError`，并在错误信息中回显示例格式。
- `synthetic_interval` 语法：实现阶段统一支持 `Ns/Nmin/Nh`（N 为正整数）。
- 解析失败策略开关命名：建议固定为 `on_timestamp_parse_error = "raise" | "exclude"`。
