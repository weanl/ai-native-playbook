# M2-024 MVP 页面规格

## 范围重置

M2-024 当前只聚焦 MVP：基于一次导入的多天数据，完成端到端算法实验与算法效果对比，并在实验前配置 auto-active 策略。

本阶段不设计模型注册、manual promotion、生产 active pointer 修改、回滚、在线 serving 或生产流量切换。后续承接主流程另开设计。

## 核心流程

```text
Import Multi-Day Dataset
-> Schema & Quality Check
-> Build Day Partitions
-> Configure Experiment Policy
-> Freeze Experiment Context
-> Rolling Train / Validate / Active / Infer Loop
-> Prediction Ledger
-> Metrics & Algorithm Ranking
```

关键规则：

- 导入数据包含多天，因此同一次实验会产生多次训练与推理循环。
- 默认训练周期为 1 天，后续可配置。
- 默认 auto-active 策略为“最新训练模型自动成为下一时间段 active 模型”，后续可配置门槛。
- 对 cutoff day `D`，使用 `<= D` 的数据构造训练集与验证集，训练模型 `M_D`。
- `M_D` 默认在 `D` 之后到下一次训练前的时间段生效。
- 推理时按样本 `timestamp` 命中 `active.effective_range`，使用对应 `active_model_id` 计算 `predicted_label` 与 `score`。
- 缺少覆盖某时间段的 active 模型时，该时间段标记 `blocked`，不参与自动 active 策略统计。

流程图 source of truth：

- `docs/product/ui/offline-model-lifecycle.drawio`

## 信息架构

主导航：

```text
Overview
Data
Policy
Rolling Experiment
Results
```

独立异常页不作为一级页面。异常与排除原因以内联区块承载：Data 展示分区质量原因，Rolling Experiment 展示当前循环阻断/部分失败，Results 汇总 excluded / blocked items。

核心对象：

- `dataset_version`：一次导入后的数据版本。
- `day_partition`：按天切分后的实验分区。
- `experiment_policy`：训练周期、auto-active 策略、质量门槛。
- `algorithm_config`：算法名、参数、seed。
- `day_cycle`：某个 cutoff day 的训练、验证、active 更新与推理循环。
- `active_interval`：`active_model_id` 的生效时间段。
- `prediction_ledger`：按 timestamp 保存的推理结果。
- `experiment_report`：算法效果对比与策略模拟摘要。

## Overview

页面目标：

- 一眼说明 MVP 范围和滚动实验逻辑。
- 展示当前导入数据覆盖的天数、实验策略和算法排行摘要。

用户动作：

- 从流程步骤进入 Data、Policy、Rolling Experiment 或 Results。
- 启动示例滚动实验。

核心信息：

- 数据覆盖范围：例如 `2026-05-01 ~ 2026-05-07`。
- 默认策略：`1 天训练一次`、`latest model auto-active`。
- 当前 active timeline 摘要。
- 算法排行前三名。

下一步动作：

- `Inspect dataset` -> `Data`
- `Configure policy` -> `Policy`
- `Run rolling experiment` -> `Rolling Experiment`
- `View results` -> `Results`

## Data

页面目标：

- 解释导入数据如何变成可滚动实验的多日分区。

用户动作：

- 查看 schema、质量分、label coverage。
- 查看每天的数据行数和是否可参与实验。

核心信息：

- Dataset summary：版本、时间范围、行数、metric 列、label 覆盖率。
- Day partition table：日期、行数、label coverage、质量状态。
- Invalid partition reason：缺失 label、schema 异常、缺 active baseline 等。

下一步动作：

- `Use valid partitions` -> `Policy`

## Policy

页面目标：

- 在实验前配置训练周期与 auto-active 策略。
- 明确策略会在实验上下文中冻结，避免实验过程中因结果变化而改变规则。

用户动作：

- 查看或调整训练周期。
- 查看 auto-active 默认策略。
- 查看质量门槛和后续可配置项。

核心信息：

- Training cadence：默认 `1 day`。
- Auto-active policy：默认 `latest trained model becomes active for next interval`。
- Future gates：`min_metric_delta`、`max_regression`、`min_label_coverage`、`quality_gate`。
- Initial active model：用于第一个可推理时间段的基线模型。

下一步动作：

- `Freeze policy` -> `Rolling Experiment`

## Rolling Experiment

页面目标：

- 展示算法/参数组合如何在多天数据上滚动训练、验证、自动 active 与推理。

用户动作：

- 选择算法配置。
- 单步推进 cutoff day。
- 查看某天的 train / validate / active / infer 结果。

核心信息：

- Algorithm matrix：算法、参数、seed。
- Day cycle：`D`、训练数据范围、验证数据范围、模型 ID、active interval。
- Active inference：推理时间段、命中的 `active_model_id`、预测数量。
- Prediction ledger preview：timestamp、active_model_id、predicted_label、score、label。

下一步动作：

- `Continue next day`
- `Open results` -> `Results`

## Results

页面目标：

- 汇总多日滚动实验结果，对比不同算法与参数效果。

用户动作：

- 按算法、参数、日期查看指标。
- 查看 active switch timeline。
- 比较候选算法配置。

核心信息：

- Metrics：`precision`、`recall`、`f1`、`pa_f1`、`fp`、`fn`、`label_coverage`。
- Ranking：按整体 PA-F1、稳定性、退化项排序。
- Active timeline：每天使用的 active 模型。
- Policy summary：`auto_active_count`、`blocked_count`、`needs_review_count`。
- Excluded / blocked items：被排除日期、算法配置、原因、是否参与指标。

下一步动作：

- `Choose candidate algorithm config`
- 后续另行进入模型生命周期主流程设计。
