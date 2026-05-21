# Tasks - Proposal ID: M2-024

## Proposal 检查清单

| # | 任务 | 模块 | 状态 | 备注 |
|---|---|---|---|---|
| 1 | 收敛为 5-tab workflow 信息架构 | changes | done | 统一两套并行方案 |
| 2 | 明确滚动策略作为实验配置/任务/结果的关键要素 | changes | done | 不作为独立页面 |
| 3 | 明确多天导入与多日训练/推理循环 | changes | done | cutoff day D 语义 |
| 4 | 明确 auto-active 默认策略 | changes | done | 默认最新训练模型自动 active |
| 5 | 明确推理结果计算逻辑 | changes | done | timestamp 命中 active interval |

## Implementation 清单

| # | 任务 | 模块 | 状态 | 备注 |
|---|---|---|---|---|
| 1 | 用户旅程（M1.6 + M2 滚动实验） | docs/product/ui | done | 5-tab 旅程 + 滚动实验旅程 |
| 2 | 页面规格（5-tab + 滚动策略要素） | docs/product/ui | done | 数据接入/预览/配置/任务/结果 |
| 3 | 交互状态模型 | docs/product/ui | done | 含滚动相关状态 |
| 4 | 视觉规范 | docs/product/ui | done | 实验工作台风格 |
| 5 | 技术取舍 | docs/product/ui | done | 静态原型 + 后续 Streamlit MVP |
| 6 | drawio 流程图 | docs/product/ui | done | 竖向主流程，无交叉长连线 |
| 7 | HTML 原型 | docs/product/ui/prototype | done | 单文件、自包含、5-tab workflow |

## 验证步骤

1. `xmllint --noout docs/product/ui/offline-model-lifecycle.drawio`
2. 检查 HTML 原型无 CDN、远程字体、外部 JS、外部 CSS 或网络请求。
3. 检查 HTML 原型包含数据接入、数据预览、实验配置、任务管理、结果查看五个 tab。
4. 检查实验配置 tab 包含滚动策略面板（训练周期、active 策略、质量门禁）。
5. 检查 HTML 原型不包含 Models、History、manual promotion、rollback 等后续主流程页面。
6. `git diff --check`

## 回滚计划

- 回滚 `changes/proposed/ui-product-design-prototype/` 与 `docs/product/ui/` 的文档和原型改动。
- 本 change 无运行时影响。
