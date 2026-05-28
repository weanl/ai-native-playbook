# Spec Diff - Proposal ID: M2-026

## Before
平台当前支持单次实验、批量实验、bundle 实验。M2-025 已新增日分区和累计训练窗口等数据层能力，但还没有执行引擎消费这些能力。

```text
读取数据 -> 单次/批量实验

滚动数据层：
  build_day_partitions(...)
  partition_tables(...)
  cumulative_training_window(...)
  split_train_validate(...)

尚无 rolling loop
尚无 auto-active model interval
尚无 prediction ledger
尚无 rolling leaderboard
```

## After
平台新增离线滚动实验执行引擎，基于 M2-025 数据层原语完成滚动训练、验证、推理与汇总。

```text
读取数据
  -> 构建有效日分区
  -> 对每个 cutoff day D:
       window <= D
       切分 train / validate
       训练每个算法
       validate 并计算 PA 指标
       latest 模型在 (D, next_D] 自动 active
       对 active interval 推理
       写入 prediction ledger
  -> 汇总 cycles
  -> 生成 active timeline
  -> 生成跨日 leaderboard
  -> 持久化 rolling records
```

## Diff Summary
- **Added**:
  - pipeline 层滚动实验数据模型。
  - `run_rolling_experiment(...)` 编排入口。
  - latest-model auto-active 策略。
  - 带 `active_model_id` 的 prediction ledger。
  - 基于跨日 PA-F1 的 rolling leaderboard。
  - additive SQLite 表：rolling experiments、cycles、predictions。
  - CLI 命令：`rolling`、`list-rolling`。
- **Removed**：无。
- **Changed**：
  - `pipeline/__init__.py` 可导出 rolling engine API。
  - `storage/schema.sql` 可新增 rolling 表。
  - CLI 命令注册可暴露 rolling 命令。

## Breaking Changes
- 预期无破坏性变更。
- **迁移路径**：现有单次、批量、bundle workflow 保持不变。

## Compatibility
- **向后兼容**：是。
- **版本影响**：M2。

## 契约说明
- 不修改 `core/` 既有接口。
- 算法 I/O 仍然统一使用 `Table`。
- 引擎使用现有算法 registry 和参数归一化能力。
- 模型 artifact 持久化不在本 proposal 范围。
- 生产 active pointer、manual promotion、rollback、scheduler、REST API 均不在范围内。
