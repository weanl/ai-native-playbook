# Tasks: rolling-experiment-workbench

## 实现清单

| 序号 | 任务 | 文件 | 状态 | 红线映射 |
| --- | --- | --- | --- | --- |
| 1 | 增加 Streamlit “滚动实验工作台”入口与 5-tab 结构 | `src/nextaiops_algo/ui/app.py` | pending | R6：仅改 UI 范围 |
| 2 | 数据接入 tab 复用输入能力并展示日分区质量 | `src/nextaiops_algo/ui/app.py` | pending | R2/R6：只调用 pipeline，不写算法逻辑 |
| 3 | 数据预览 tab 复用现有预览并补充分区质量摘要 | `src/nextaiops_algo/ui/app.py` | pending | R6：不重写无关页面 |
| 4 | 实验配置 tab 支持算法选择、滚动策略、冻结策略 | `src/nextaiops_algo/ui/app.py` | pending | R3：参数与策略显式化 |
| 5 | 任务管理 tab 调用 `run_rolling_experiment` 并展示 cycle / active model / blocked 状态 | `src/nextaiops_algo/ui/app.py` | pending | R2/R3：业务逻辑留在 pipeline |
| 6 | 结果查看 tab 展示 leaderboard、active timeline、prediction ledger、失败汇总 | `src/nextaiops_algo/ui/app.py` | pending | R3：实验结果可追踪 |
| 7 | 增加滚动工作台 UI 集成测试 | `tests/integration/test_rolling_workbench_ui.py` | pending | R4/R5：新增能力有测试，不改弱断言 |
| 8 | 运行验证并记录结果 | N/A | pending | R4/R5：make test/lint/smoke/demo |

## 验证方式

实现 PR 需运行：

```bash
make test
make lint
make smoke
make demo
```

如 Windows PowerShell 缺少 `make`，使用 WSL 中的 `make` 运行同等命令。

## 回滚方案

回滚 implementation PR 中对以下文件的修改：

- `src/nextaiops_algo/ui/app.py`
- `tests/integration/test_rolling_workbench_ui.py`

proposal 文档可保留为历史记录，或随 implementation 回滚一并删除。

## 停下条件

触发以下任一情况应停止实现并报告：

- 需要修改 `core/` 既有接口。
- 需要新增运行时依赖。
- 需要改变 M2-026 rolling engine 契约。
- 现有单算法实验、批量实验、历史记录出现回归且无法在 2 次尝试内修复。
- `make test` / `make lint` / `make smoke` 连续失败 2 次。
