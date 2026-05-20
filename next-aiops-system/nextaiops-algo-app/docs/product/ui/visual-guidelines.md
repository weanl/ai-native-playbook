# M2-024 MVP 视觉规范

## 设计目标

MVP 原型应像一个实验工作台，而不是模型生命周期管理后台。

视觉重点：

- 快速看懂导入数据覆盖几天。
- 快速看懂滚动训练和推理时间线。
- 快速比较不同算法效果。
- 明确 blocked / partial_failed 的原因。

## 信息密度

- 首屏展示流程、策略摘要和当前实验状态。
- 表格以扫描为主，避免大块解释文案。
- 指标卡只展示 MVP 关键指标：PA-F1、F1、Recall、FP、blocked days。

## 颜色

| 用途 | 建议颜色 |
|---|---|
| 数据与分区 | 蓝色系 |
| 策略与 active | 紫色系 |
| 推理与指标 | 绿色系 |
| 复核与注意 | 黄色系 |
| 阻断与失败 | 红色系 |
| 辅助信息 | 灰色系 |

避免整页单一色调。策略、数据、结果应能被颜色区分。

## 页面组件

### 流程条

用于展示：

```text
Data -> Policy -> Rolling Experiment -> Results
```

当前步骤高亮，已完成步骤用完成态。

### Day Partition 表

列建议：

```text
day / rows / label coverage / quality / status / usage
```

### Active Timeline

必须清楚展示：

```text
model_id
effective_from
effective_to
inference_rows
```

### Prediction Ledger

列建议：

```text
timestamp / active_model_id / algorithm / params / predicted_label / score / label
```

### Algorithm Ranking

列建议：

```text
rank / algorithm / params / PA-F1 / F1 / Recall / FP / blocked days / stability
```

## 原型约束

- 单文件 HTML。
- 不依赖 CDN、远程字体、外部 JS、外部 CSS 或网络请求。
- 可直接浏览器打开。
- 桌面宽屏和常见笔记本视口可读。
- 不展示后续模型注册、manual promotion、回滚或生产发布页面。
