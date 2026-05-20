# M2-024 MVP 交互状态模型

## 状态分层

MVP 只保留与滚动算法实验相关的状态：

```text
UI 状态
数据分区状态
策略状态
日循环状态
active 区间状态
实验结果状态
```

## UI 状态

| 状态 | 含义 | 页面表现 |
|---|---|---|
| `empty` | 尚未导入数据或无筛选结果 | 空状态 + 下一步入口 |
| `loading` | 页面或组件加载中 | loading / skeleton |
| `running` | 滚动实验正在执行 | 当前 day 高亮，关键配置 disabled |
| `failed` | 当前步骤失败 | 错误摘要 + 定位上下文 |
| `partial_failed` | 部分算法/日期失败 | 成功结果保留，失败项以内联提示和结果页排除项呈现 |
| `completed` | 实验完成 | 结果表、排行与报告入口 |

## 数据分区状态

| 状态 | 含义 | 是否参与实验 |
|---|---|---|
| `valid` | schema 与质量满足要求 | 是 |
| `low_label_coverage` | label 覆盖不足 | 可解释，不参与自动 active 统计 |
| `invalid` | schema 或质量阻断 | 否 |
| `blocked` | 缺少 active model 覆盖或策略阻断 | 否 |

## 策略状态

| 状态 | 含义 | 用户动作 |
|---|---|---|
| `draft` | 策略尚未冻结 | 可调整 cadence / auto-active 策略 |
| `frozen` | 实验上下文已冻结 | 不可在运行中修改 |
| `simulated` | 已产生策略模拟摘要 | 查看 auto_active / blocked / needs_review |

默认策略：

- `training_cadence = 1 day`
- `auto_active = latest_trained_model`

## 日循环状态

| 状态 | 含义 | 输出 |
|---|---|---|
| `pending` | 尚未进入该日循环 | 无 |
| `training` | 正在用 `<= D` 的数据训练 | model pending |
| `validating` | 正在验证 `M_D` | validation metrics |
| `active_assigned` | `M_D` 已成为下一时间段 active | active interval |
| `inferring` | 正在对下一时间段推理 | prediction ledger |
| `completed` | 该日循环完成 | daily metrics |
| `blocked` | 数据或 active 覆盖不满足 | blocked reason / excluded items |

## Active 区间状态

| 状态 | 含义 |
|---|---|
| `covered` | timestamp 能命中一个 active interval |
| `missing` | timestamp 不属于任何 active interval |
| `overlap` | 多个 active interval 重叠，需要阻断并修正 |

推理规则：

```text
prediction.timestamp ∈ active.effective_range
=> use active_model_id
=> output predicted_label / score
```

## 结果状态

| 状态 | 含义 |
|---|---|
| `ranked` | 算法配置已完成指标排序 |
| `needs_review` | 指标有退化或覆盖不足 |
| `candidate_config` | 可作为后续主流程输入的候选算法配置 |

## 禁用规则

- 策略未冻结时，不能启动滚动实验。
- 数据没有有效 day partition 时，不能启动滚动实验。
- 某时间段缺少 active model 时，该时间段推理结果必须标记 `blocked`。
- `unlabeled` 或 label coverage 不足时，不得把 F1 / PA-F1 作为自动 active 决策依据。
