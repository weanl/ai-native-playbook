# M2-024 页面规格

## 范围

原型对齐当前 Streamlit UI 的交互闭环：数据接入、数据预览、实验配置、任务管理、结果查看。同时承载 M2 滚动实验能力，滚动策略作为实验配置、任务管理、结果查看中的关键要素。

本阶段不设计生产模型注册、manual promotion、生产 active pointer 修改、回滚、在线 serving 或流量切换。

## 信息架构

单页面 + workflow tab：

```text
指标异常检测实验
  └─ 数据接入
  └─ 数据预览
  └─ 实验配置
  └─ 实验任务管理
  └─ 实验结果查看
```

侧边栏展示品牌标识 + 功能页面入口 + 主流程摘要。

异常不作为独立页面，以内联区块承载：schema 异常在数据接入回显表展示，failed cell 在结果页 Cell 明细展示。

核心对象：

- `data_source`：CSV / .out / npy/npz / zip / 内置数据集。
- `DatasetBundle`：多文件 bundle，schema 一致性校验后形成实验输入。
- `DayPartition`：多天数据的日分区，用于滚动实验。
- `algorithm_config`：算法名、参数（元信息驱动表单）、REGISTRY 来源。
- `experiment_policy`：实验策略配置，含滚动策略（训练周期、active 策略、质量门禁）。
- `experiment_task`：单算法 / 多算法 / 滚动实验任务，承载子任务矩阵。
- `batch_result`：批量实验结果（排行榜 / 矩阵 / 钻取 / Cell 明细）。
- `prediction_ledger`：滚动实验推理结果记录（timestamp / algorithm / params / cutoff_day / active_model_id / predicted_label / score / label）。

## 数据接入

页面目标：

- 选择数据来源，展示上传文件回显和 schema 状态。

核心信息：

- 数据来源下拉（CSV / .out / npy/npz / zip / 内置数据集）。
- DatasetBundle：文件列表、处理方式（DatasetBundle member / Table input）、schema ok badge。
- 单表：文件名、schema ok badge。
- notice 说明后续实验走哪条路径（run_experiment / run_bundle_experiment / run_batch / run_batch_bundle / rolling_experiment）。

## 数据预览

页面目标：

- 让用户在运行实验前理解数据质量和指标走势。

核心信息：

- 预览文件选择（bundle 时可切换，单文件时 disabled）。
- 4 个指标卡：行数、列数、指标列数、真实异常点数。
- 3 个 tab：指标曲线（Plotly fake）、字段质量（角色/dtype/缺失率/唯一值）、数据样例。
- 多天数据时：日分区列表（日期、行数、label coverage、质量状态、排除原因）。

## 实验配置

页面目标：

- 配置实验类型、算法和参数，可选配滚动策略，创建实验任务。

核心信息：

- 实验类型切换：单算法实验 / 多算法实验 / 滚动实验。
- 算法选择下拉（主算法 + 参数预览）。
- 多算法时：批量算法范围勾选（check-card）+ 任务矩阵提示。
- 算法参数表单（元信息驱动：number input / enum select）。
- 实验标识 notice。
- **滚动策略配置（右侧面板，滚动实验时必填）**：
  - 滚动模式：累积（默认） / 滑动窗口。
  - 训练窗口长度（默认 1 天）。
  - active 策略：latest model auto-active（默认）。
  - 质量门禁：label coverage 门槛、schema 完整性检查。
- 创建实验任务面板：输入/算法/策略 3 个指标卡 + 操作按钮。

## 任务管理

页面目标：

- 展示实验任务状态和子任务矩阵。

核心信息：

- 任务列表表：实验任务标识、数据标识、算法标识、类型 badge（单算法/多算法/滚动）、状态 badge、子任务数、操作按钮。
- 子任务抽屉（drawer）：cell 级行列表（算法 × 文件 × 状态 × run_id/error）。
- **滚动任务特有信息**：
  - 当前 cutoff day 进度。
  - active model 状态（哪个模型正在 active）。
  - blocked 时间段（缺少 active 模型覆盖的区间）。
  - 部分失败算法的 partial_failed 状态。

## 结果查看

### 单算法结果

- 实验完成 notice（run_id）。
- 4 个指标卡：真实异常点 / 算法检出点 / TP / FP。
- 指标含义表：Precision / Recall / F1 / PA-F1 + 含义说明。
- 结果曲线 fake-chart（iframe viz.html）。

### 多算法批量结果

- 批量数据集结果标题 + summary 信息行。
- 4 个指标卡：算法数 / 文件数 / 成功单元 / 失败单元。
- 4 个 tab：
  - 总排行榜：algorithm / mean F1 / mean PA-F1 / completed / failed。
  - 算法×文件矩阵：矩阵指标下拉 + 文件×算法值表 + heatmap fake-chart。
  - 文件钻取：文件选择下拉 + overlay fake-chart。
  - Cell 明细：算法 / 文件 / 状态 / run_id / F1 / PA-F1 / 错误。

### 滚动实验结果

- 滚动实验 summary：cutoff day 数量、active model 数量、prediction ledger 条目数。
- **Active Timeline**：每天使用的 active 模型（时间轴展示）。
- **Prediction Ledger 预览**：timestamp / algorithm / cutoff_day / active_model_id / predicted_label / score / label。
- **算法跨日排行**：跨日 mean PA-F1、稳定性、success_rate。
- **排除项汇总**：blocked 时间段、failed 算法、无效分区原因（内联展示）。
