# Tasks - Proposal ID: M2-024

## Proposal 检查清单

| # | 任务 | 模块 | 状态 | 备注 |
|---|---|---|---|---|
| 1 | 将范围收敛为滚动算法实验 MVP | changes | done | 删除过早的模型生命周期主流程 |
| 2 | 明确多天导入与多日训练/推理循环 | changes | done | cutoff day D 语义 |
| 3 | 明确 auto-active 默认策略 | changes | done | 默认最新训练模型自动 active |
| 4 | 明确推理结果计算逻辑 | changes | done | timestamp 命中 active interval |
| 5 | 明确原型页面边界 | changes | done | Data / Policy / Rolling Experiment / Results，异常说明内联展示 |

## Implementation 清单

| # | 任务 | 模块 | 状态 | 备注 |
|---|---|---|---|---|
| 1 | 刷新用户旅程 | docs/product/ui | done | 输出 MVP 旅程 |
| 2 | 刷新页面规格 | docs/product/ui | done | 输出 MVP 页面信息架构 |
| 3 | 刷新交互状态模型 | docs/product/ui | done | 数据分区、策略、日循环、active 区间 |
| 4 | 刷新视觉规范 | docs/product/ui | done | 实验工作台风格 |
| 5 | 刷新技术取舍 | docs/product/ui | done | 静态原型 + 后续 Streamlit MVP |
| 6 | 优化 drawio 流程图 | docs/product/ui | done | 竖向主流程，无交叉长连线 |
| 7 | 重建 HTML 原型 | docs/product/ui/prototype | done | 删除旧复杂原型，生成 MVP 原型 |

## 验证步骤

1. `xmllint --noout docs/product/ui/offline-model-lifecycle.drawio`
2. 检查 HTML 原型无 CDN、远程字体、外部 JS、外部 CSS 或网络请求。
3. 检查 HTML 原型包含 Data、Policy、Rolling Experiment、Results，不包含独立异常页面。
4. 检查 HTML 原型不包含 Models、History、manual promotion、rollback 等后续主流程页面。
5. `git diff --check`

## 回滚计划

- 回滚 `changes/proposed/ui-product-design-prototype/` 与 `docs/product/ui/` 的文档和原型改动。
- 本 change 无运行时影响。
