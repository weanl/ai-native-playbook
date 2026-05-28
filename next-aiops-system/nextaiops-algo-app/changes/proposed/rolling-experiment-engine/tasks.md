# Tasks - Proposal ID: M2-026

## Implementation Checklist

| # | Task | Module | Status | Notes |
|---|------|--------|--------|-------|
| 1 | 新增滚动执行模型 | pipeline/rolling.py | pending | `AlgorithmConfig`、`ExperimentPolicy`、`RollingExperiment`、`RollingDayCycle`、ledger 和 leaderboard row |
| 2 | 基于 M2-025 数据层实现 cutoff-day 迭代 | pipeline/rolling.py | pending | 使用 `build_day_partitions`、`partition_tables`、`cumulative_training_window`、`split_train_validate` |
| 3 | 实现按算法配置训练与 validate | pipeline/rolling.py | pending | 使用 registry factory、归一化参数、计算 validate PA 指标 |
| 4 | 实现 latest auto-active interval | pipeline/rolling.py | pending | D 日训练模型覆盖 `(D, next_D]`；缺失覆盖标记为 blocked |
| 5 | 实现 active interval 推理与 prediction ledger | pipeline/rolling.py | pending | ledger 包含 timestamp、cutoff_day、active_model_id、prediction、score、label |
| 6 | 实现 partial failure 语义 | pipeline/rolling.py | pending | 单算法失败不阻断其他算法；cycle/experiment 状态反映部分可用输出 |
| 7 | 实现 rolling leaderboard 聚合 | pipeline/rolling.py | pending | 按 mean PA-F1、median PA-F1、success_rate 排序 |
| 8 | 新增 rolling 记录的 additive SQLite 持久化 | storage/schema.sql, storage/sqlite_tracking.py | pending | 不改变现有 `runs`、`metrics`、`batches`、`batch_runs` 行为 |
| 9 | 导出 rolling engine API | pipeline/__init__.py | pending | 显式导出，避免隐式入口 |
| 10 | 新增 CLI 命令 | cli/commands.py, cli/__main__.py | pending | `rolling`、`list-rolling`；算法名逗号分隔 |
| 11 | 单测覆盖 policy、active interval、ledger、leaderboard、失败处理 | tests/unit/test_rolling_engine.py | pending | 覆盖 blocked 和 partial_failed 场景 |
| 12 | 集成测试覆盖 2 算法 x 3 天数据 | tests/integration/test_rolling_engine_e2e.py | pending | 断言 cycles、ledger、leaderboard、persistence |
| 13 | CLI 集成测试 | tests/integration/test_rolling_cli.py | pending | rolling 命令可跑通，list 命令可返回新建 rolling experiment |

## Verification Steps
1. Run `make test` -> 现有测试和新增测试全部通过。
2. Run `make lint` -> ruff 和 mypy 通过。
3. Run `make smoke` -> 现有单次实验 smoke 保持绿色。
4. 手动检查一个 rolling result：
   - 每个 cutoff day 有 train / validate / active / infer 元数据；
   - D 日 active interval 指向 `@D` 模型；
   - ledger 行包含 `active_model_id`；
   - leaderboard 排序与 PA-F1 指标一致。

## Rollback Plan
- 删除 `pipeline/rolling.py` 及对应测试。
- 移除 rolling CLI 命令注册。
- 回滚 additive SQLite 表定义和相关 store 方法。
- 现有 single、batch、bundle experiment 表保持兼容。

## Dependencies
- **Blocked by**: M2-025 rolling experiment data layer（已合入）。
- **Blocks**: M2-027 rolling experiment workbench。
