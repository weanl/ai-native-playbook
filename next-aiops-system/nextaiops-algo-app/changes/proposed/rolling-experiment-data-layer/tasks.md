# Tasks - Proposal ID: M2-025

## Implementation Checklist

| # | Task | Module | Status | Notes |
|---|------|--------|--------|-------|
| 1 | 新增 `PartitionStatus` 枚举 + `DayPartition` 数据模型 | pipeline/rolling_data.py | pending | pydantic BaseModel |
| 2 | 实现 `build_day_partitions` | pipeline/rolling_data.py | pending | 按日期列分组 + 质量检查 |
| 3 | 实现 `partition_tables` | pipeline/rolling_data.py | pending | 仅返回 valid 分区 |
| 4 | 实现 `cumulative_training_window` | pipeline/rolling_data.py | pending | 合并 <= cutoff_day 分区 |
| 5 | 实现 `split_train_validate` | pipeline/rolling_data.py | pending | 复用 split_by_time 逻辑 |
| 6 | 单元测试：分区构建 + 质量检查 + 边界 | tests/unit/test_rolling_data.py | pending | 无 timestamp / 无 label / 空分区 / 全排除 |
| 7 | 集成测试：多天 CSV → 分区 → 窗口 → 切分 | tests/integration/test_rolling_data_e2e.py | pending | 端到端数据流 |

## Verification Steps
1. Run `make test` → All tests pass
2. Run `make lint` → No errors
3. Run `make smoke` → All algorithms pass
4. 手动验证：构造 3 天 CSV，确认分区数量与窗口拼接正确

## Rollback Plan
- 删除 `pipeline/rolling_data.py` 与对应测试文件
- 无既有代码被修改，回滚零风险

## Dependencies
- **Blocked by**: 无
- **Blocks**: M2-026（滚动实验引擎）
