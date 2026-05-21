# Spec Diff - Proposal ID: M2-024

## 变更前

旧版设计存在两套并行方案：

```text
方案 A（原 PLAN 描述）：
Data / Policy / Rolling Experiment / Results 四页面

方案 B（实际 HTML 原型）：
数据接入 / 数据预览 / 实验配置 / 任务管理 / 结果查看 五 tab
```

两套方案对滚动策略的定位不一致：方案 A 将 Policy 作为独立页面，方案 B 将滚动策略作为实验配置中的可选面板。

## 变更后

以实际 HTML 原型为准，统一为 5-tab workflow：

```text
数据接入
数据预览
实验配置
实验任务管理
实验结果查看
```

滚动策略（day partition、cutoff day、auto-active、prediction ledger）作为**实验配置、任务管理、结果查看中的关键要素**，不是独立页面。

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

## 新增要求

- 默认训练周期：1 天。
- 默认 auto-active：最新训练模型自动成为下一时间段 active。
- 推理结果必须按 `timestamp -> active_model_id` 计算。
- Prediction ledger 必须能追溯 `timestamp / algorithm / params / cutoff_day / active_model_id / predicted_label / score / label`。
- drawio 使用无交叉竖向主流程，避免线框重叠。
- 静态原型为单文件、自包含、无外部依赖。

## 非目标

以下能力不进入当前原型：

```text
生产模型注册
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
