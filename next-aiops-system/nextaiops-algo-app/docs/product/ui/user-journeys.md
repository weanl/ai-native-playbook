# M2-024 MVP 用户旅程

## 目标

本阶段用户旅程聚焦一个 MVP 问题：

```text
一次导入多天数据后，平台如何按日滚动训练模型、自动切换实验 active 模型、对后续时间段推理，并比较不同算法效果？
```

本文只定义产品旅程和原型叙事，不定义后端 schema，不实现生产模型生命周期。

## 角色

### 平台评估者

关注点：

- 是否能从导入数据跑完端到端算法实验。
- 是否能解释多天数据上的训练、active、推理循环。
- 是否能公平比较不同算法效果。

### 算法工程师

关注点：

- 每个算法/参数组合在不同日期的指标变化。
- 训练集、验证集、推理区间是否清楚。
- 推理结果使用的是哪个时间段的 active 模型。

### AIOps 运维人员

关注点：

- 默认策略是否可理解：一天一训、最新模型自动 active。
- 哪些日期或算法组合被 blocked。
- 哪个算法配置更适合进入后续主流程。

## MVP 演示主线

### 1. Data：导入多天数据

演示目标：

- 展示一次导入包含多天数据。
- 展示 schema、quality、label coverage。
- 把导入数据切成 `D1...DN` 日分区。

关键叙事：

- 每天都可能触发一次训练与推理循环。
- 不合格分区在 Data 页内联展示原因，不参与自动 active 策略统计。

### 2. Policy：实验前配置策略

演示目标：

- 先配置策略，再跑实验。
- 默认 `1 天训练一次`。
- 默认 `最新训练模型自动成为下一时间段 active 模型`。

关键叙事：

- 策略在实验上下文里冻结。
- 本阶段只是实验 active，不修改生产 active pointer。
- 后续可把训练周期和策略门槛做成配置项。

### 3. Rolling Experiment：按日滚动实验

演示目标：

- 对每个 cutoff day `D`，使用 `<= D` 的数据训练和验证模型 `M_D`。
- `M_D` 默认成为 `D` 之后到下一次训练前的 active 模型。
- 使用这个 active 模型对后续时间段推理。

关键叙事：

```text
cutoff = D
train_validate_data = rows[timestamp <= D]
active_interval = (D, next_training_day]
prediction_data = rows[timestamp in active_interval]
prediction_model = M_D
```

### 4. Results：比较算法效果

演示目标：

- 展示每个算法/参数组合的多日推理结果。
- 汇总日指标与整体指标。
- 输出候选算法配置排行。

关键叙事：

- 推理结果不是用最终模型扫全量数据。
- 每条预测都必须能追溯到当时生效的 `active_model_id`。
- 算法对比基于同样的滚动规则和同样的数据分区。

## 推理结果计算逻辑

对每个算法/参数组合：

```text
for D in imported_days:
    train_data = rows where timestamp <= D
    validation_data = validation split inside train_data
    M_D = train(algorithm, params, train_data)
    validate(M_D, validation_data)

    active_interval = (D, next_training_day]
    set_experiment_active(M_D, active_interval)

    inference_rows = rows where timestamp in active_interval
    predictions = detect(M_D, inference_rows)
    append prediction ledger
```

Prediction ledger 至少包含：

```text
timestamp
algorithm
params
cutoff_day
active_model_id
predicted_label
score
label
```

## 异常旅程

### 数据分区无效

```text
day partition invalid -> rolling cycle skipped -> Data inline reason + Results excluded items
```

原因可能是 schema 不完整、label coverage 不足或数据质量低。

### 缺少 active 模型覆盖

```text
timestamp not in any active interval -> prediction blocked -> excluded from auto-active stats
```

页面必须说明缺失的时间段，而不是静默跳过。

### 算法组合失败

```text
algorithm config failed on day D -> keep other configs running -> mark partial_failed
```

成功组合仍可参与排行，失败组合在 Rolling Experiment 当前循环提示与 Results excluded items 中展示。
