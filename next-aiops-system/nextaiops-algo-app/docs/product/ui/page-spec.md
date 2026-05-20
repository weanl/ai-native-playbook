# M2-024 页面规格

## 信息架构

主导航：

```text
Overview
Data
Experiments
Batch Compare
Continuous Learning
Models
History
Settings
```

跨页面核心对象：

- `dataset version`：数据版本，承载 schema、fingerprint、质量摘要。
- `experiment run`：单算法实验运行。
- `batch run`：批量实验运行。
- `train job`：持续学习训练任务。
- `model version`：模型版本，包含 candidate、active、superseded 等状态。
- `promotion event`：晋级或回滚审计事件。
- `artifact`：图表、评估结果、训练输出等可追溯产物。

术语边界：

- `active model` 表示模型注册表中的当前生效版本，不表示在线推理服务或生产流量切换。
- `promote` 表示候选模型通过证据评审并触发生命周期事件，不表示 M2 实现发布系统。

HTML 原型演示样例：

- 示例对象：`Checkout API latency`。
- 示例数据版本：`ds-2026.05.18`。
- 示例算法配置：`IQR / window=96`。
- 示例训练任务：`job-20260519-01`。
- 示例候选模型：`model-2026.05.19-c1`。
- 示例审计事件：`evt-901`。

原型应支持用户通过“下一步 / 上一步 / 直接点击步骤”完成：

```text
Overview -> Data -> Experiments -> Batch Compare -> Continuous Learning -> Models -> History
```

离线 model 生命周期应以训练数据集、训练任务、模型 artifact、模型版本注册和晋级事件为主轴。推荐先以 drawio 作为流程 source of truth，再回填 HTML 原型：

```text
Daily Data Partition -> Training Dataset Version -> Train Job -> Model Artifact
-> Model Version(candidate) -> Offline Evaluation / Evidence -> Manual Promotion
-> Active Model / Archived Previous Model
```

`experiment run` 与 `batch run` 是探索、算法参数选择和证据引用来源，不应被表达为 model artifact 的直接生产步骤。

每日新增数据后的自动训练、评估与 `auto-active` 策略可以在流程图中作为 M2+ / 演示策略模拟支线表达，但不得混同为 M2-028 当前实现范围。M2-028 的主线仍是 manual promotion。

流程图文件：`docs/product/ui/offline-model-lifecycle.drawio`。

## Overview

页面目标：

- 让用户在 30 秒内理解当前系统状态。
- 展示 active model、最近训练、最近实验和待处理事件。

用户动作：

- 查看 active model。
- 进入待复核 candidate model。
- 进入失败 train job 或 partial failed batch run。
- 跳转到 Data / Models / History。

核心信息：

- Active model card：版本、算法、生效时间、最近指标。
- Candidate review card：候选模型数量、证据完整度、是否可晋级。
- Recent train jobs：状态、输入数据版本、输出模型版本。
- System status：数据质量、最近失败、artifact 状态。

下一步动作：

- `Review candidate` -> `Models`
- `Inspect data` -> `Data`
- `Open history` -> `History`

代表性状态：

- 正常：active model 健康，最近训练完成。
- running：存在 training / evaluating 任务。
- attention：存在 evidence incomplete 或 partial_failed。
- empty：尚无模型版本。

## Data

页面目标：

- 解释模型学习的数据来源。
- 展示 dataset version 是否可用于训练、评估和晋级证据。

用户动作：

- 查看数据版本列表。
- 查看 schema、fingerprint、质量摘要。
- 选择数据版本进入实验或持续学习视图。

核心信息：

- Dataset version table：版本、时间范围、行数、指标列、状态、质量分。
- Schema panel：timestamp、metric、label 角色推断。
- Fingerprint panel：hash、统计摘要、缺失值、异常比例。
- Usage panel：被哪些 experiment、batch、train job、model version 使用。

下一步动作：

- `Run experiment` -> `Experiments`
- `Compare algorithms` -> `Batch Compare`
- `Use in training window` -> `Continuous Learning`

代表性状态：

- `draft`：导入中或未验证。
- `validated`：可用于实验和训练。
- `invalid`：质量不足，相关动作 disabled。
- `archived`：仅可追溯。

## Experiments

页面目标：

- 重构单算法实验页，让用户清楚看到输入、参数、结果和诊断。

用户动作：

- 选择 dataset version。
- 选择算法与参数。
- 查看运行结果、指标、异常点和 artifact。

核心信息：

- Input summary：数据版本、时间范围、metric 列、label 可用性。
- Algorithm panel：算法、参数、随机种子、输入角色要求。
- Result chart：时间序列、异常点、阈值线。
- Metrics panel：Precision、Recall、F1、PA-F1 等已支持指标，并说明 `evaluation mode`、`label coverage` 与指标可信度。
- Diagnostics panel：失败原因、退化提示、artifact 链接。

下一步动作：

- `Add to batch compare` -> `Batch Compare`
- `Open run history` -> `History`

代表性状态：

- empty：未选择数据。
- running：实验运行中。
- failed：schema 不合法、算法失败或 artifact 缺失。
- completed：可查看结果与 artifact。

## Batch Compare

页面目标：

- 承载多算法、多参数或多数据版本的批量评估。
- 帮用户识别稳定候选，而不只看单次最高分。

用户动作：

- 选择批量实验结果。
- 查看排行榜、矩阵、热力图。
- 定位 partial_failed 的组合。
- 选择候选配置进入持续学习。

核心信息：

- Leaderboard：算法、参数、数据版本、指标、状态。
- Metric matrix：不同算法和数据版本的横向比较。
- Heatmap：性能分布与异常组合。
- Failure panel：失败组合、错误摘要、影响范围。

下一步动作：

- `Use as candidate direction` -> `Continuous Learning`
- `Inspect failed run` -> `History`

代表性状态：

- running：批量实验未完成。
- partial_failed：部分组合失败，但成功结果可查看。
- failed：全部失败或配置不可用。
- completed：结果完整。

## Continuous Learning

页面目标：

- 展示持续学习如何从数据窗口产生 train job 与 candidate model。
- 明确训练任务状态与模型生命周期状态的区别。

用户动作：

- 查看 rolling window。
- 查看 train job 队列。
- 查看训练输入、评估输入和输出 artifact。
- 跳转到 candidate model。

核心信息：

- Window timeline：训练窗口、评估窗口、回测窗口。
- Train job table：状态、输入数据版本、算法配置、输出模型版本。
- Job detail：参数、metrics、artifact、错误信息。
- Candidate output：是否生成 candidate model，证据是否完整。

下一步动作：

- `Review candidate` -> `Models`
- `Inspect failed job` -> `History`

代表性状态：

- `queued`
- `training`
- `evaluating`
- `completed`
- `failed`
- `cancelled`

## Models

页面目标：

- 展示模型版本列表和 candidate vs active 对比。
- 用 evidence panel 支撑晋级或复核判断。

用户动作：

- 选择 candidate model。
- 对比 active model。
- 查看 evidence panel。
- 在证据充分时发起 promote。
- 在需要时查看 rollback 目标。

核心信息：

- Model version table：版本、算法、训练数据、评估数据、状态、创建时间。
- Candidate vs active comparison：指标差异、退化项、稳定性提示。
- Evidence panel：
  - 训练数据版本。
  - 评估数据版本。
  - 回测窗口。
  - 标签覆盖率。
  - 评估模式：`labeled` / `unlabeled` / `proxy`。
  - 指标可信度。
  - candidate vs active 指标差异。
  - 退化项。
  - 数据质量摘要。
  - 漂移或分布变化提示。
  - 模型 artifact ID / path / checksum / version。
  - 算法名称、参数、seed。
  - train job ID 与 experiment run ID。
  - artifact 链接。
  - promote / rollback 审计记录。
- Action panel：promote、request review、rollback。

下一步动作：

- evidence sufficient -> `Promote candidate`
- evidence incomplete -> 回到缺失证据来源页面
- rollback investigation -> `History`

代表性状态：

- `candidate`
- `rejected`
- `promoted`
- `active`
- `superseded`
- `archived`
- `rolled_back`

不可晋级规则：

- 缺少训练数据版本。
- 缺少评估数据版本或回测窗口。
- 缺少标签覆盖率或评估模式说明。
- `unlabeled` 或 `proxy` 模式下将 F1 / PA-F1 直接作为晋级证据。
- 指标存在关键退化但无说明。
- 数据质量 invalid。
- 关键 artifact 缺失。
- 模型 artifact 缺少 ID、路径、checksum 或版本。
- 缺少 algorithm / params / seed / train_job_id / run_id 等复现字段。

## History

页面目标：

- 统一查询 run、batch、train job、promotion event。
- 支持从历史事件回到证据链。

用户动作：

- 按对象类型、状态、时间过滤。
- 查看 promotion / rollback 审计记录。
- 跳回相关数据、模型或训练任务。

核心信息：

- Timeline：事件类型、状态、关联对象、操作者、时间。
- Audit detail：动作、原因、前后版本、证据摘要。
- Trace links：dataset、run、batch、job、model、artifact。

History event 最低字段：

- `event_id`
- `event_type`
- `subject_type`
- `subject_id`
- `source_model_version`（promotion / rollback 事件适用）
- `target_model_version`（promotion / rollback 事件适用）
- `actor`
- `reason`
- `created_at`
- `related_refs`
- `related_artifacts`

下一步动作：

- `Open model evidence` -> `Models`
- `Open train job` -> `Continuous Learning`
- `Open dataset` -> `Data`

代表性状态：

- empty：无历史记录。
- filtered empty：筛选条件无结果。
- rollback：展示回滚原因和目标版本。

## Settings

页面目标：

- 承载低频配置说明与只读演示配置。
- M2-024 原型不实现真实配置保存。

用户动作：

- 查看 mock 环境配置。
- 查看未来权限、审计、数据保留策略入口。

核心信息：

- Environment：demo / local。
- Retention placeholder：artifact 与 history 保留策略。
- Governance placeholder：权限、审批、审计入口。

下一步动作：

- 无强主线动作，作为辅助页面存在。

代表性状态：

- readonly：当前为静态原型，不保存配置。
