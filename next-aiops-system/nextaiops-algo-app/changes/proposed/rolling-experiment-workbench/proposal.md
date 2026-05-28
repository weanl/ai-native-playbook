# Proposal ID: M2-027

## 标题
滚动实验工作台

## 动机
- **为什么做**：M2-025 已提供日分区与累计训练窗口，M2-026 已提供滚动实验执行引擎、auto-active 策略、prediction ledger 与 leaderboard，但这些能力仍停留在 pipeline / CLI 层。M2-024 已确认继续使用 Streamlit 落地 MVP，并采用“数据接入 / 数据预览 / 实验配置 / 实验任务管理 / 实验结果查看”的 5-tab workflow。现在需要把滚动实验串成可操作、可评审、可 demo 的工作台。
- **影响**：用户可以在 Streamlit 中完成“导入多天数据 -> 查看日分区质量 -> 配置算法与滚动策略 -> 执行滚动实验 -> 查看排行、active timeline、prediction ledger”的端到端闭环，同时保留现有单算法实验、批量实验、历史记录能力。

## 范围
- **影响模块**：ui、tests、docs。
- **计划新增/修改文件**：
  - `src/nextaiops_algo/ui/app.py`
  - `tests/integration/test_rolling_workbench_ui.py`
  - `changes/proposed/rolling-experiment-workbench/proposal.md`
  - `changes/proposed/rolling-experiment-workbench/spec-diff.md`
  - `changes/proposed/rolling-experiment-workbench/tasks.md`
- **依赖**：
  - M2-024：`changes/proposed/ui-product-design-prototype/` 与 `docs/product/ui/`。
  - M2-025：`src/nextaiops_algo/pipeline/rolling_data.py`。
  - M2-026：`src/nextaiops_algo/pipeline/rolling.py` 与 SQLite 滚动实验记录能力。
- **新增依赖**：不新增运行时依赖。

## 设计

### 信息架构

在现有 Streamlit 应用内新增“滚动实验工作台”入口，并在该入口内落地 M2-024 的 5-tab workflow：

```text
滚动实验工作台
  ├─ 数据接入
  ├─ 数据预览
  ├─ 实验配置
  ├─ 实验任务管理
  └─ 实验结果查看
```

现有“单算法实验 / 批量实验 / 历史记录”入口继续保留，避免一次性重写已稳定的 M1.6 功能。M2-027 的重点是把滚动实验 MVP 跑通；后续如要把全部实验类型统一进同一个工作台，可另开 proposal。

### 数据接入

复用现有上传与内置数据集能力，把输入转换为 `Table` 后调用 M2-025 数据层：

- `build_day_partitions(table, date_column=...)`
- `partition_tables(table, partitions)`

页面展示：

- 数据来源、文件名、schema 推断摘要。
- 日分区列表：`date`、`row_count`、`label_count`、`label_coverage`、`status`、`exclusion_reason`。
- 无效分区以内联 warning 展示排除原因。
- 如果输入无法形成有效日分区，禁用后续滚动实验执行按钮，并显示可定位原因。

### 数据预览

复用现有 `_render_data_preview` 能力展示曲线、字段质量与数据样例，并额外展示滚动实验相关质量摘要：

- 有效日分区数、无效日分区数、总行数、真实异常点数。
- 日分区质量表。
- 对滚动实验不适用的数据给出 inline warning，而不是抛出页面级异常。

### 实验配置

配置项来自 M2-026 执行引擎：

- 算法多选：来自 `algorithms.registry.REGISTRY`。
- 算法参数：MVP 先使用各算法默认参数，保留参数 JSON 文本框作为高级入口。
- 滚动策略：
  - `cadence="1d"` 固定展示，不提供其它 cadence。
  - `validate_ratio` 使用 number input。
  - `label_coverage_threshold` 使用 number input 或留空。
  - `auto_active="latest"` 固定展示。
  - `on_algorithm_error="partial_failed"` 固定展示。

页面需要支持“冻结策略”语义：冻结后把当前数据摘要、算法列表和策略写入 session state，作为执行任务的不可变输入。编辑配置会让冻结状态失效，要求用户重新冻结。

### 实验任务管理

任务管理 tab 负责触发 `run_rolling_experiment(...)` 并展示返回结果：

- 运行按钮：仅在存在有效日分区、至少选择 1 个算法、策略已冻结时启用。
- 运行结果 summary：`experiment_id`、`status`、cutoff day 数量、active model 数量、prediction ledger 条目数。
- cycle 表：`cutoff_day`、`train_rows`、`validate_rows`、`active_interval_start`、`active_interval_end`、`status`、`exclusion_reason`。
- partial failed / blocked 状态以内联 warning 展示，不吞掉底层错误信息。

MVP 可以使用 Streamlit 同步执行，不引入后台任务、队列或调度器。

### 实验结果查看

结果 tab 展示 M2-026 结果对象与 SQLite 记录：

- leaderboard：`algorithm_name`、`params`、`mean_pa_f1`、`median_pa_f1`、`success_rate`、`cycles_completed`、`cycles_failed`。
- active timeline：按 cutoff day 展示 active interval 与 active model。
- prediction ledger 预览：`timestamp`、`algorithm_name`、`cutoff_day`、`active_model_id`、`predicted_label`、`score`、`label`。
- 排除项汇总：blocked interval、invalid partition、failed algorithm 与原因。

如缺少 score 或 label，UI 应优雅降级为空值展示，不改变 pipeline 契约。

### 存储与历史

滚动实验执行后继续由 M2-026 的 SQLite tracking 负责落库。UI 只读取：

- `SqliteTrackingStore.list_rolling_experiments(...)`
- `SqliteTrackingStore.count_rolling_predictions(...)`

本 change 不新增持久化表，不改变 `runs`、`batches`、`rolling_experiments`、`rolling_predictions` schema。

### 错误处理

- UI 捕获用户输入类错误并展示 `st.warning` / `st.error`。
- pipeline 抛出的业务异常必须显示上下文，不改写为含糊提示。
- 不使用 broad `except` 吞异常；如需捕获，必须捕获具体异常类型或在 UI 边界重新显示原始错误信息。

## 非目标

本 change 不做：

- 重新定义 M2-024 已完成的信息架构。
- 生产模型注册、manual promotion、回滚页面。
- 在线推理服务、REST API、自动调度。
- 权限、多租户、多人审批。
- React / Next.js 迁移。
- 新增 `core/` 稳定契约。
- 新增运行时依赖。

## 备选方案

- **直接重写现有 Streamlit 首页为统一 5-tab 工作台**：暂缓。现有单算法、批量实验、历史记录已经可用，M2-027 先用独立滚动工作台入口降低回归风险。
- **只提供 CLI，不做 UI**：拒绝。M2-027 的价值就是把滚动实验 MVP 变成可 demo 的产品闭环。
- **引入后台任务框架**：拒绝。M2 MVP 面向小规模 demo，同步执行足够，后台任务会扩大范围。

## 权衡

- 独立入口会让 UI 短期存在“旧实验页 + 新滚动工作台”两套入口，但能最大限度保护现有功能。
- 参数表单首版以默认参数为主，会限制算法调参深度；滚动实验 MVP 先验证闭环，细粒度参数矩阵后置。
- Streamlit 同步执行不适合长任务，但符合 M2 小数据 demo 目标。

## 验收标准
- [ ] Streamlit 可完整走通：导入多天数据 -> 数据预览 -> 配置策略 -> 滚动实验 -> 查看排行。
- [ ] 数据接入页展示日分区与质量状态。
- [ ] 实验配置页展示滚动策略配置并可冻结。
- [ ] 实验任务管理页展示 cutoff day 进度与 active model 状态。
- [ ] 实验结果查看页展示 leaderboard、active timeline、prediction ledger。
- [ ] partial_failed、blocked、invalid partition 能在 UI 中可见。
- [ ] 单算法实验页、批量实验页、历史记录不回归。
- [ ] UI 不直接写滚动实验业务逻辑，只调用 pipeline / storage / viz。
- [ ] 不修改 `core/` 既有接口。
- [ ] 测试通过：`make test`。
- [ ] 静态检查通过：`make lint`。
- [ ] 冒烟通过：`make smoke`。
- [ ] `make demo` 可启动并走通滚动实验 MVP。

## 时间线
- **预计工作量**：proposal review 后 1 个 implementation PR。
- **依赖状态**：M2-024、M2-025、M2-026 均已合入。

## 关联
- 设计依据：`changes/proposed/ui-product-design-prototype/`、`docs/product/ui/`。
- 执行层依据：`changes/proposed/rolling-experiment-engine/`。
- 讨论：对应 `docs/PLAN.md` 中 `M2-027：rolling-experiment-workbench`。
