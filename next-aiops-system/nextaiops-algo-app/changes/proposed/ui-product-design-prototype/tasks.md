# Tasks - Proposal ID: M2-024

## Proposal 检查清单

| # | 任务 | 模块 | 状态 | 备注 |
|---|------|------|------|------|
| 1 | 定义 M2-024 动机、范围、非目标与验收标准 | changes | done | 仅 proposal，不写实现代码 |
| 2 | 定义设计交付物与原型契约 | changes | done | 后续 implementation 仅限 `docs/product/ui/` |
| 3 | 定义 spec 影响与兼容性 | changes | done | 无运行时行为变更 |
| 4 | 定义 implementation 任务计划与验证步骤 | changes | done | 等待 proposal review |
| 5 | 明确 proposal 与后续设计交付物以中文为主 | changes | done | 路径、代码标识符、命令与必要技术名词可保留英文 |
| 6 | 补充模型晋级证据、领域生命周期状态与技术选型 rubric | changes | done | 基于 proposal review 意见 |
| 7 | 补充实验优先闭环、离线策略模拟与效果指标范围 | changes | done | 明确 M2 做 dry-run / backtest / recommendation，不做无人值守真实 auto-active |

## Proposal 通过后的 Implementation 清单

| # | 任务 | 模块 | 状态 | 备注 |
|---|------|------|------|------|
| 1 | 编写用户角色、客户演示主线与核心旅程 | docs/product/ui | pending | 输出 `user-journeys.md` |
| 2 | 编写全局导航、页面职责与低保真页面规格 | docs/product/ui | pending | 输出 `page-spec.md` |
| 3 | 设计实验优先闭环与离线策略模拟旅程 | docs/product/ui | pending | 覆盖不同数据集、算法、参数、候选方向、策略模拟和 winning config |
| 4 | 定义策略模拟效果指标 | docs/product/ui | pending | 覆盖 F1 / PA-F1、误报漏报、跨数据集稳定性、active timeline、数据可信度 |
| 5 | 设计候选模型晋级 evidence panel | docs/product/ui | pending | 覆盖数据版本、回测窗口、指标差异、退化项、artifact 与审计记录 |
| 6 | 编写交互状态模型 | docs/product/ui | pending | 输出 `interaction-states.md`，区分 UI 状态、任务状态、生命周期状态和策略模拟指标 |
| 7 | 编写视觉规范 | docs/product/ui | pending | 输出 `visual-guidelines.md` |
| 8 | 编写 Streamlit 与正式前端的技术选型评估 | docs/product/ui | pending | 输出 `tech-decision.md`，必须包含 rubric 与结论 |
| 9 | 绘制离线模型生命周期与策略模拟流程图 | docs/product/ui | pending | 输出 `offline-model-lifecycle.drawio` |
| 10 | 使用 mock 数据构建自包含本地静态 HTML 原型 | docs/product/ui/prototype | pending | 输出 `prototype/index.html`，不得依赖 CDN 或网络 |
| 11 | 手动验证本地原型导航、状态展示与视口适配 | docs/product/ui/prototype | pending | 验证桌面宽屏与常见笔记本视口 |
| 12 | 确认 implementation 只修改 `docs/product/ui/` | repository | pending | 不得修改 `src/`、`tests/`、`storage/schema.sql`、`pyproject.toml` |

## 验证步骤
1. 对照 `docs/PLAN.md` 中 M2-024 范围锚点，review `changes/proposed/ui-product-design-prototype/proposal.md`。
2. review `changes/proposed/ui-product-design-prototype/spec-diff.md`，确认无运行时、API、存储或依赖影响。
3. review `changes/proposed/ui-product-design-prototype/tasks.md`，确认 implementation 边界清晰。
4. 后续 implementation PR 中，直接用浏览器打开 `docs/product/ui/prototype/index.html`，验证所有主页面可本地切换。
5. 后续 implementation PR 中，验证原型展示 `empty`、`loading`、`running`、`failed`、`partial_failed`、`candidate`、`active`、`archived` 等状态。
6. 后续 implementation PR 中，验证 `Models` 页面包含候选模型晋级 evidence panel，且 evidence 不足时不会呈现为可直接晋级。
7. 后续 implementation PR 中，验证 `interaction-states.md` 区分 UI 通用状态、训练任务状态、模型生命周期状态与晋级事件状态。
8. 后续 implementation PR 中，验证 `page-spec.md` 与 `user-journeys.md` 明确实验优先闭环、`Strategy Simulation` 一级模块和最终承接闭环。
9. 后续 implementation PR 中，验证离线策略模拟输出效果指标，不只输出策略决策。
10. 后续 implementation PR 中，验证 `offline-model-lifecycle.drawio` 可打开且流程图无明显线框重叠。
11. 后续 implementation PR 中，验证 `tech-decision.md` 按 rubric 给出推荐方案、妥协项与迁移触发条件。
12. 后续 implementation PR 中，确认 `prototype/index.html` 不依赖 CDN、远程字体、外部 JS、外部 CSS 或网络请求。
13. 后续 implementation PR 中，运行 `git diff --name-only`，确认只修改 `docs/product/ui/` 文件。

## 回滚计划
- 回滚 `changes/proposed/ui-product-design-prototype/` 目录。
- 本 proposal 无运行时影响，因此无需数据、代码、依赖或 schema 迁移。

## 依赖关系
- **前置依赖**：无。
- **阻塞对象**：`M2-029 continuous-learning-workbench-implementation`。
