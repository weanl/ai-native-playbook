# Spec Diff - Proposal ID: M2-024

## 变更前
当前 UI 基线是从 M0 到 M1.6 逐步演进出来的 Streamlit demo / workbench，主要围绕已实现能力组织：

```text
单算法实验
批量实验
批量可视化
结果诊断
算法参数元数据
数据预览
```

当前产品体验尚未具备经过 review 的 M2 持续学习信息架构，也没有正式定义模型版本、晋级、回滚与客户演示叙事。

当前 UI 也没有把 M2 当前阶段的实验优先范围表达清楚：

```text
不同数据集上的算法实验
批量比较与候选方向选择
每日新增数据后的离线策略模拟
策略模拟效果指标与推荐结论
最终模型生命周期主流程承接
```

当前 UI 也没有明确区分：

```text
通用 UI 状态：loading / failed / empty
长任务状态：queued / training / evaluating
领域生命周期状态：candidate / active / superseded / rolled_back
晋级决策证据：数据版本 / 回测窗口 / 指标差异 / 退化项 / 审计记录
```

## 变更后
M2-024 在实现前新增设计规格层：

```text
changes/proposed/ui-product-design-prototype/
  proposal.md
  spec-diff.md
  tasks.md

docs/product/ui/
  user-journeys.md
  page-spec.md
  interaction-states.md
  visual-guidelines.md
  tech-decision.md
  offline-model-lifecycle.drawio
  prototype/index.html
```

proposal 通过后的 implementation 将定义以下页面的产品设计与本地静态原型：

```text
Overview
Data
Experiments
Batch Compare
Strategy Simulation
Continuous Learning
Models
History
Settings
```

每个页面必须说明：

```text
页面目标
用户动作
核心信息
下一步动作
代表性状态
```

`Models` 与 `History` 相关设计必须定义候选模型晋级证据包：

```text
训练数据版本
评估数据版本
回测窗口
candidate vs active 指标差异
退化项
数据质量摘要
漂移或分布变化提示
关键 artifact 链接
promote / rollback 审计记录
```

M2-024 还必须定义实验优先闭环与离线策略模拟：

```text
Data
→ Experiments
→ Batch Compare
→ Candidate Direction
→ Strategy Simulation
→ Winning Config
```

离线策略模拟必须输出数据实验效果指标：

```text
precision / recall / f1 / pa_f1
误报数 / 漏报数
跨 dataset version / rolling window 稳定性
would_promote_count / needs_review_count / blocked_count
模拟 active timeline
相对当前 active 的指标 delta
label_coverage / evaluation mode / data quality / drift
```

真实无人值守 `auto-active` 不进入 M2 当前实现范围；M2 只要求设计并后续支持 dry-run / backtest / recommendation 形态的离线策略模拟。

`interaction-states.md` 必须区分以下状态层次：

```text
UI 通用状态
数据版本状态
训练任务状态
模型版本状态
晋级事件状态
```

`tech-decision.md` 必须按 rubric 评估 UI 技术选型：

```text
多页面信息架构
长任务状态刷新
Plotly / 大表格交互
状态管理
组件复用
离线 demo 成本
部署复杂度
未来认证 / 权限 / 审计扩展
M2 时间成本
M3 可演进性
```

原型仅作为设计产物：

```text
不修改 src/
不修改 tests/
不修改 storage schema
不修改 pyproject
不调用后端
不新增依赖
不依赖 CDN / 外部 JS / 外部 CSS / 远程字体
```

## 差异摘要
- **新增**：
  - `changes/proposed/ui-product-design-prototype/` 下的 M2-024 proposal 包。
  - `docs/product/ui/` 下的后续设计文档契约。
  - `docs/product/ui/offline-model-lifecycle.drawio` 的离线模型生命周期与策略模拟流程图契约。
  - `docs/product/ui/prototype/index.html` 的后续静态原型契约。
  - proposal 与后续 M2-024 设计交付物以中文为主的语言约定。
  - 实验优先闭环与 M2 离线策略模拟设计要求。
  - 策略模拟效果指标和数据可信度指标要求。
  - 候选模型晋级 evidence panel 的设计要求。
  - UI 通用状态、长任务状态与领域生命周期状态的分层要求。
  - UI 技术选型 rubric。
  - 静态 HTML 原型自包含、无网络依赖的约束。
- **移除**：
  - 无。
- **变更**：
  - 不改变运行时行为。
  - 不改变 UI 实现行为。
  - 不改变 public API 或存储契约。

## 破坏性变更
- 无。
- **迁移路径**：不适用。本 change 只提出设计交付物。

## 兼容性
- **向后兼容**：是。
- **版本影响**：M2。
