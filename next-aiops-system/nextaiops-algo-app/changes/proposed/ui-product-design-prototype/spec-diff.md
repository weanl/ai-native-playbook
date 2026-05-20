# Spec Diff - Proposal ID: M2-024

## 变更前

旧版设计过早引入：

```text
Continuous Learning
Models
History
manual promotion
model version
rollback
active pointer 主流程
```

这导致原型偏离当前最需要确认的 MVP：导入数据后的滚动算法实验与 auto-active 策略计算。

## 变更后

M2-024 设计收敛为：

```text
Data
Policy
Rolling Experiment
Results
```

异常说明不再作为独立一级页面，而是嵌入 Data、Rolling Experiment 与 Results。

核心流程：

```text
Import Multi-Day Dataset
-> Build Day Partitions
-> Configure Experiment Policy
-> Freeze Experiment Context
-> for each cutoff day D:
     train/validate M_D using rows <= D
     set M_D active for next interval
     infer rows in that active interval
-> Prediction Ledger
-> Metrics & Ranking
```

## 新增要求

- 默认训练周期：1 天。
- 默认 auto-active：最新训练模型自动成为下一时间段 active。
- 推理结果必须按 `timestamp -> active_model_id` 计算。
- Prediction ledger 必须能追溯 `timestamp / algorithm / params / cutoff_day / active_model_id / predicted_label / score / label`。
- drawio 使用无交叉竖向主流程，避免线框重叠。
- 静态原型删除旧复杂页面，重建 MVP 页面。

## 非目标

以下能力不进入当前原型：

```text
模型注册
manual promotion
回滚
生产 active pointer 修改
online serving
流量切换
多租户权限
```

## 兼容性

- 不改变运行时行为。
- 不改变 public API。
- 不改变存储 schema。
