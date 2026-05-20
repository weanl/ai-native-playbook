# Proposal ID: M2-024

## 标题
滚动算法实验与 auto-active 策略模拟 MVP 原型

## 动机

- **为什么做**：M2 当前需要先讲清楚“导入多天数据后，如何按日滚动训练、验证、自动 active、推理并比较算法效果”。此前把后续模型生命周期主流程放得过早，导致原型复杂且偏离 MVP。
- **影响**：评审者能先确认端到端算法实验和 active 策略计算逻辑，再决定后续是否承接模型注册、晋级、回滚等主流程。

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

## MVP 设计

核心流程：

```text
Import Multi-Day Dataset
-> Build Day Partitions
-> Configure Policy
-> Freeze Experiment Context
-> Rolling Train / Validate / Active / Infer Loop
-> Prediction Ledger
-> Metrics & Algorithm Ranking
```

关键规则：

- 一次导入数据包含多天，因此一次实验会产生多次训练与推理循环。
- 默认训练周期为 1 天，后续可配置。
- 默认 auto-active 策略为最新训练模型自动成为下一时间段 active。
- 对 cutoff day `D`，使用 `<= D` 的数据训练与验证 `M_D`。
- `M_D` 在 `D` 之后到下一次训练前的时间段生效。
- 推理时按样本 `timestamp` 命中 active interval，使用对应 `active_model_id` 输出 `predicted_label` 和 `score`。

## 验收标准

- [ ] 文档明确 MVP 不包含后续模型生命周期主流程。
- [ ] 文档明确多天导入、多日滚动训练与推理循环。
- [ ] 文档明确默认 1 天训练一次。
- [ ] 文档明确默认最新训练模型自动成为下一时间段 active。
- [ ] 文档明确推理结果按 `timestamp -> active_model_id` 计算。
- [ ] drawio 流程清晰，无明显线框重叠。
- [ ] HTML 原型为单文件、自包含、无外部依赖。
- [ ] HTML 原型可演示 Data、Policy、Rolling Experiment、Results，并在相关页面内联展示 blocked / partial_failed 原因。
- [ ] HTML 原型不展示 Models、History、manual promotion、回滚或生产发布页面。

## 相关信息

- 范围锚点：`docs/PLAN.md` 中的 `M2-024: ui-product-design-prototype`。
