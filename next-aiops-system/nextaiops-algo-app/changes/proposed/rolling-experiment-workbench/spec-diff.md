# Spec Diff: rolling-experiment-workbench

## 新增能力

平台新增 Streamlit 滚动实验工作台，在 UI 层承接 M2-025 日分区数据层与 M2-026 滚动实验执行引擎。

## UI

### 新增：滚动实验工作台入口

现有 Streamlit sidebar 增加“滚动实验工作台”入口。进入后展示 5 个 workflow tab：

1. 数据接入
2. 数据预览
3. 实验配置
4. 实验任务管理
5. 实验结果查看

现有“单算法实验”“批量实验”“历史记录”页面必须继续可用。

### 新增：数据接入 tab

数据接入 tab 必须：

- 复用现有上传 / 内置数据集输入能力。
- 展示 schema 推断摘要。
- 调用 pipeline 数据层生成日分区。
- 展示日分区质量表。
- 在无有效分区时阻止创建滚动实验任务。

### 新增：数据预览 tab

数据预览 tab 必须：

- 复用现有曲线、字段质量、数据样例展示。
- 展示滚动实验质量摘要。
- 展示日分区状态与排除原因。

### 新增：实验配置 tab

实验配置 tab 必须：

- 从 `REGISTRY` 读取算法列表。
- 支持选择至少 1 个算法。
- 支持配置 `validate_ratio` 和 `label_coverage_threshold`。
- 明示 `cadence=1d`、`auto_active=latest`、`on_algorithm_error=partial_failed`。
- 支持冻结策略；未冻结策略时不得运行滚动实验。

### 新增：实验任务管理 tab

实验任务管理 tab 必须：

- 调用 `run_rolling_experiment(...)` 执行滚动实验。
- 展示 experiment summary。
- 展示每个 cutoff day 的 cycle 状态。
- 展示 active interval 与 active model。
- 展示 blocked / partial_failed / failed 信息。

### 新增：实验结果查看 tab

实验结果查看 tab 必须展示：

- leaderboard。
- active timeline。
- prediction ledger 预览。
- 排除项与失败原因汇总。

## Pipeline / Storage

UI 必须复用已有 pipeline 与 storage API：

- `build_day_partitions`
- `partition_tables`
- `run_rolling_experiment`
- `SqliteTrackingStore.list_rolling_experiments`
- `SqliteTrackingStore.count_rolling_predictions`

UI 不新增滚动实验业务计算逻辑，不直接读写 SQLite 表。

## Compatibility

本 change 不改变：

- `core/` 契约。
- 现有单算法实验 pipeline。
- 现有批量实验 pipeline。
- 现有 run / batch / rolling SQLite schema。
- CLI 行为。

## 测试要求

- 新增 UI helper 或 workflow 级集成测试，覆盖滚动工作台依赖的状态组装与结果展示数据准备。
- 保留现有单算法、批量、历史记录测试。
- `make test`、`make lint`、`make smoke` 必须通过。
- `make demo` 必须可启动，并可手工走通滚动实验 MVP。
