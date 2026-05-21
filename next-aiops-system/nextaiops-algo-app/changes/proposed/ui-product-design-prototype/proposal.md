# Proposal ID: M2-024

## 标题
M2 实验工作台 UI 产品设计 + 可评审 HTML 原型

## 动机

- **为什么做**：M2 阶段需要一个统一的实验工作台，承载 M1.6 批量实验能力，同时承载 M2 滚动实验（按日训练、auto-active 策略、prediction ledger）能力。此前存在两套并行设计（四页面 vs 五 tab），需要收敛。
- **影响**：评审者能确认端到端实验工作台的信息架构、关键页面、核心流程、视觉规范、交互状态，作为 M2-027 Streamlit 实现的依据。

## 范围

- **影响模块**：仅产品设计文档与静态 HTML 原型。
- **本 proposal 修改文件**：
  - `changes/proposed/ui-product-design-prototype/proposal.md`
  - `changes/proposed/ui-product-design-prototype/spec-diff.md`
  - `changes/proposed/ui-product-design-prototype/tasks.md`
- **implementation 允许修改文件**：
  - `docs/product/ui/user-journeys.md`
  - `docs/product/ui/page-spec.md`
  - `docs/product/ui/interaction-states.md`
  - `docs/product/ui/visual-guidelines.md`
  - `docs/product/ui/tech-decision.md`
  - `docs/product/ui/offline-model-lifecycle.drawio`
  - `docs/product/ui/prototype/index.html`

## 非目标

- 不修改 `src/`、`tests/`、`storage/schema.sql`、`pyproject.toml`。
- 不实现生产模型注册、manual promotion、回滚、online serving 或流量切换。
- 不自动修改真实生产 active pointer。
- 不引入前端工程或新依赖。

## 信息架构（以 HTML 原型为准）

单页面 + workflow tab，侧边栏承载品牌与入口：

```text
指标异常检测实验
  └─ 数据接入
  └─ 数据预览
  └─ 实验配置
  └─ 实验任务管理
  └─ 实验结果查看
```

侧边栏展示品牌标识 + 功能页面入口 + 主流程摘要。

异常不作为独立页面，以内联区块承载：schema 异常在数据接入回显表展示，failed cell 在结果页 Cell 明细展示。

## 滚动策略作为关键要素

滚动策略（M2 MVP 核心）不作为独立页面，而是作为以下三个 tab 的关键要素：

**实验配置**：
- 右侧面板配置滚动策略：滚动模式（累积/滑动）、训练窗口长度、active 策略（latest model auto-active）、质量门禁。
- 创建实验任务时展示策略摘要。

**实验任务管理**：
- 滚动任务类型：单日实验 / 批量实验 / 滚动实验。
- 滚动任务状态：显示当前 cutoff day、active model、blocked 时间段。

**实验结果查看**：
- 滚动任务结果：active timeline（每天使用的 active 模型）、prediction ledger 预览、算法跨日排行。
- blocked / partial_failed 原因内联展示。

## MVP 设计

核心流程：

```text
Import Dataset（单文件 / DatasetBundle / 多天数据）
-> Build DatasetBundle / Day Partitions
-> Configure Experiment Policy（含滚动策略）
-> Create Experiment Task
-> Rolling Train / Validate / Active / Infer Loop
-> Prediction Ledger
-> Metrics & Algorithm Ranking
```

关键规则：

- 数据来源支持：CSV / .out / npy/npz / zip / 内置数据集 / DatasetBundle。
- 单文件场景：走现有 `run_experiment` / `run_batch` 路径。
- 多文件场景：走 `run_bundle_experiment` / `run_batch_bundle` 路径。
- 多天数据场景：按日构建 day partition，配置滚动策略后执行滚动实验。
- 默认训练周期为 1 天，后续可配置。
- 默认 auto-active 策略为最新训练模型自动成为下一时间段 active。
- 对 cutoff day `D`，使用 `<= D` 的数据训练与验证 `M_D`。
- `M_D` 在 `D` 之后到下一次训练前的时间段生效。
- 推理时按样本 `timestamp` 命中 active interval，使用对应 `active_model_id` 输出 `predicted_label` 和 `score`。

## 验收标准

- [x] 文档明确 MVP 不包含生产模型生命周期主流程（模型注册、manual promotion、回滚）。
- [x] 文档明确 5-tab workflow 信息架构。
- [x] 文档明确滚动策略作为实验配置/任务管理/结果查看的关键要素，不是独立页面。
- [x] 文档明确默认 1 天训练一次。
- [x] 文档明确默认最新训练模型自动成为下一时间段 active。
- [x] 文档明确推理结果按 `timestamp -> active_model_id` 计算。
- [x] drawio 流程清晰，无明显线框重叠。
- [x] HTML 原型为单文件、自包含、无外部依赖。
- [x] HTML 原型可演示数据接入、数据预览、实验配置、任务管理、结果查看，并在相关页面内联展示 blocked / partial_failed 原因。
- [x] HTML 原型不展示 Models、History、manual promotion、回滚或生产发布页面。

## 相关信息

- 范围锚点：`docs/PLAN.md` 中的 `M2-024: ui-product-design-prototype`。
