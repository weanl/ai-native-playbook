# M2-024 交互状态模型

## 状态分层

原型覆盖的状态层：

```text
UI 状态
数据状态
实验任务状态
算法状态
cell 状态
```

## UI 状态

| 状态 | 含义 | 原型表现 |
|---|---|---|
| `empty` | 尚未导入数据 | notice 占位："运行实验后将在这里展示检测摘要、指标解释和结果曲线。" |
| `running` | 批量实验正在执行 | progress bar + 进度文字："正在运行 6/9：iqr × 180_SMD..." |
| `completed` | 实验完成 | 指标卡 + 指标表 + 结果曲线 |
| `completed_with_failures` | 部分算法/文件失败 | warning badge + 成功结果保留 + failed cell 可钻取 |

## 数据状态

| 状态 | 含义 | 原型表现 |
|---|---|---|
| `upload_ok` | 数据已上传并 schema 校验通过 | success badge `upload_ok=True` + `schema ok` |
| `input_bundle` | DatasetBundle 多文件 | brand badge `input_bundle` |
| `input_table` | 单表输入 | neutral badge `input_table` |

## 实验任务状态

| 状态 | 含义 | 原型表现 |
|---|---|---|
| `READY` | 任务已创建，未启动 | neutral badge |
| `COMPLETED` | 单算法实验完成 | success badge |
| `COMPLETED_WITH_FAILURES` | 多算法实验部分失败 | warning badge + "8 / 9" 子任务数 |

## 算法状态

| 状态 | 含义 | 原型表现 |
|---|---|---|
| `completed` | 算法正常完成 | 在 REGISTRY 可用 |
| `failed` | 算法训练失败 | algorithms 数据中 status 字段 |

## cell 状态（算法 × 文件）

| 状态 | 含义 | 原型表现 |
|---|---|---|
| `COMPLETED` | cell 成功 | success badge + run_id |
| `FAILED` | cell 失败 | danger badge + error message |
| `NOT_SELECTED` | 该算法未被选中 | neutral badge |
| `READY` | cell 未执行 | neutral badge |

## 禁用规则

- 未选中任何算法时，"创建并启动任务"按钮 disabled。
- 单文件时预览文件选择 disabled。
- 批量运行期间，控件锁定（M1.6 已实现）。