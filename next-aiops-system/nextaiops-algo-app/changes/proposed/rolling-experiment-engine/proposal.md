# Proposal ID: M2-026

## 标题
滚动实验执行引擎

## 动机
- **为什么做**：M2-025 已经提供日分区、累计训练窗口、时间安全的 train / validate 切分能力，但平台还缺少真正消费这些能力的执行层。当前还不能按 cutoff day 循环训练、让最新训练模型自动覆盖下一时间段、记录逐点推理结果，也不能跨天汇总算法排行。
- **影响**：本 proposal 为 M2 滚动实验 MVP 打通执行层前置能力。用户可以在离线连续学习场景下比较算法表现，而不需要先引入生产模型注册、调度器或在线服务。

## 范围
- **影响模块**：pipeline、storage、cli、tests。
- **计划新增/修改文件**：
  - `src/nextaiops_algo/pipeline/rolling.py`
  - `src/nextaiops_algo/pipeline/__init__.py`
  - `src/nextaiops_algo/storage/schema.sql`
  - `src/nextaiops_algo/storage/sqlite_tracking.py`
  - `src/nextaiops_algo/cli/commands.py`
  - `src/nextaiops_algo/cli/__main__.py`
  - `tests/unit/test_rolling_engine.py`
  - `tests/integration/test_rolling_engine_e2e.py`
  - `tests/integration/test_rolling_cli.py`
- **依赖**：不新增运行时依赖。

## 设计
### 数据模型

新增 pipeline 层 pydantic 模型。这些模型是执行记录，不是稳定 `core/` 契约。

- `AlgorithmConfig`
  - `name: str`
  - `params: dict[str, Any] = {}`
- `ExperimentPolicy`
  - `cadence: Literal["1d"]`
  - `validate_ratio: float`
  - `label_coverage_threshold: float | None`
  - `auto_active: Literal["latest"]`
  - `on_algorithm_error: Literal["partial_failed"]`
- `RollingExperiment`
  - `experiment_id: str`
  - `dataset_path: str`
  - `date_column: str | None`
  - `algorithms: list[AlgorithmConfig]`
  - `policy: ExperimentPolicy`
  - `status: Literal["completed", "partial_failed", "failed"]`
  - `created_at: datetime`
- `RollingDayCycle`
  - `cutoff_day: date`
  - `train_rows: int`
  - `validate_rows: int`
  - `active_interval_start: datetime | None`
  - `active_interval_end: datetime | None`
  - `status: Literal["completed", "partial_failed", "blocked"]`
  - `exclusion_reason: str | None`
- `PredictionLedgerRow`
  - `timestamp`
  - `algorithm_name`
  - `params`
  - `cutoff_day`
  - `active_model_id`
  - `predicted_label`
  - `score`
  - `label`
- `RollingLeaderboardRow`
  - `algorithm_name`
  - `params`
  - `mean_pa_f1`
  - `median_pa_f1`
  - `success_rate`
  - `cycles_completed`
  - `cycles_failed`

### 执行流程

`run_rolling_experiment(...)` 负责完整编排：

1. 通过现有 table loader 读取数据集。
2. 使用 M2-025 的 `build_day_partitions` 构建日分区。
3. 使用 `partition_tables` 物化有效日分区。
4. 对每个 cutoff day 执行：
   - 构建 `window = cumulative_training_window(partitions, cutoff_day)`。
   - 切分 `train, validate = split_train_validate(window, validate_ratio)`。
   - 对每个算法配置：
     - 通过现有 registry factory 创建算法实例。
     - 在 `train` 上执行 `fit`。
     - 在 `validate` 上执行 `detect`。
     - 使用现有 PA 指标计算 validate 评估结果。
     - 将内存模型保存到实验上下文：`model_id = f"{algorithm_name}[{identity_params}]@D{cutoff_day}"`。
   - 为成功训练的模型计算 active interval：`(cutoff_day, next_cutoff_day)`。
   - 对 active interval 数据执行推理，并追加 prediction ledger。
5. 汇总 day cycle、active timeline、ledger、leaderboard。
6. 将滚动实验元数据和 prediction ledger 落 SQLite。
7. 返回 `RollingExperimentResult`。

### Auto-Active 策略

MVP 只支持 `latest`：

- cutoff day `D` 训练出的模型自动成为 `(D, next_cutoff_day]` 时间段的 active 模型。
- 如果某段时间没有可用模型覆盖，则该 interval 标记为 `blocked`。
- `blocked` interval 必须在结果摘要中可见；除非明确归因到算法失败，否则不计入 leaderboard 的 success-rate 分母。

### 失败处理

- 单个算法失败不能阻断同一 cycle 内其他算法。
- 失败的算法或 cycle 记录为 `partial_failed`，并携带错误信息。
- cycle 状态：
  - `completed`：所有配置算法都产出 validate 与 active 推理结果。
  - `partial_failed`：至少一个算法失败，但至少一个算法成功。
  - `blocked`：没有 active 模型可覆盖该 interval。
- 整个 experiment 状态：
  - `completed`：所有 cycle 完成。
  - `partial_failed`：至少一个 cycle 部分失败，但仍有可用输出。
  - `failed`：没有任何 cycle 产出可用输出。

### Prediction Ledger

ledger 按 active interval 的逐点推理结果记录。多指标检测输出遵循任务契约，使用 OR 合并后的 `predicted_label`。如果结果表存在 `<metric>.anomaly_score`，MVP 记录所有 score 列的最大值；如果没有 score，则 `score` 为空。

### 算法排行

leaderboard 按算法配置聚合并排序：

1. `mean_pa_f1` 降序
2. `median_pa_f1` 降序
3. `success_rate` 降序

PA 指标来自 validate 输出。prediction ledger 主要服务 active interval 分析和后续可视化；MVP 的排行榜先基于 validate 质量，语义更稳定。

### 存储

在 SQLite 中新增滚动实验专用表：

```text
rolling_experiments(
  experiment_id primary key,
  dataset_path,
  date_column,
  policy_json,
  algorithms_json,
  status,
  created_at
)

rolling_day_cycles(
  experiment_id,
  cutoff_day,
  train_rows,
  validate_rows,
  active_interval_start,
  active_interval_end,
  status,
  exclusion_reason,
  metrics_json
)

rolling_predictions(
  experiment_id,
  timestamp,
  algorithm_name,
  params_json,
  cutoff_day,
  active_model_id,
  predicted_label,
  score,
  label
)
```

schema 变更必须是 additive，不得改变现有 `runs`、`metrics`、`batches`、`batch_runs` 行为。

### CLI

新增：

```bash
nextaiops_algo rolling \
  --data data/multi_day.csv \
  --date-column timestamp \
  --cadence 1d \
  --algos three_sigma,iqr \
  --validate-ratio 0.7 \
  --auto-active latest \
  --output ./.nextaiops_algo/rolling_results/

nextaiops_algo list-rolling --limit 10
```

`--algos` 接受逗号分隔算法名。带参数的算法配置可延后，除非能自然复用现有 CLI 参数解析能力。

### 备选方案

- **现在就持久化训练模型 artifact**：拒绝。M2 MVP 明确模型只在实验上下文内存中保持，生命周期管理后置。
- **新增 `core/` 模型**：拒绝。滚动实验执行记录尚不是跨任务稳定契约。
- **只按 active interval 预测结果排行**：暂缓。validate 指标更适合作为首版稳定排序依据；active ledger 先保留给后续 UI 诊断与分析。

### 权衡

- 内存模型让 MVP 简洁，但滚动实验暂不支持恢复执行。
- SQLite ledger 便于检查，但长数据集下行数会增长；M2 MVP 面向小规模离线 demo，接受该成本。
- 只支持 `latest` auto-active 会限制策略空间，但能让 pipeline 和 UI 语义更清晰。

## 验收标准
- [ ] 2 个算法 x 3 天数据可跑通滚动实验。
- [ ] 每个 cutoff day 记录 train / validate / active / infer 结果。
- [ ] `latest` auto-active 能让模型 `M_D` 在 `(D, next_D]` 生效。
- [ ] prediction ledger 行包含 `active_model_id`。
- [ ] 单算法失败标记 partial failure，且不阻断其他算法。
- [ ] blocked interval 有明确记录。
- [ ] leaderboard 按跨日 PA-F1 排序。
- [ ] 不破坏现有 `run_experiment`、`run_batch`、`run_batch_bundle` 行为。
- [ ] 不修改 `core/` 既有接口。
- [ ] 测试通过：`make test`。
- [ ] 静态检查通过：`make lint`。
- [ ] 冒烟通过：`make smoke`。

## 时间线
- **预计工作量**：proposal review 后 1 个 implementation PR。
- **依赖**：M2-025 数据层，已合入。

## 关联
- ADR：默认不需要；如实现阶段必须修改 `core/` 既有接口，则需先补 ADR。
- 讨论：对应 `docs/PLAN.md` 中 `M2-026：rolling-experiment-engine`。
