# M0 Skeleton — 最终架构

> NextAIOpsAlgoApp M0 Walking Skeleton 的模块关系、数据流与 Table 贯穿示意。

## 1. 模块关系

```text
┌─────────────────────────────────────────────────────────────┐
│                    NextAIOpsAlgoApp M0                       │
│                                                             │
│  ┌─────────┐  ┌───────────┐  ┌───────────┐                │
│  │  CLI    │  │ Streamlit │  │  (REST)   │  ← M1+          │
│  │ cli/    │  │  ui/      │  │           │                  │
│  └───┬─────┘  └─────┬─────┘  └───────────┘                  │
│      └───────────────┼─────────────────                     │
│                      │  (调用 pipeline，不写业务逻辑)        │
│              ┌───────▼──────────┐                            │
│              │    pipeline/     │  编排层                     │
│              │  preprocess      │  CSV → Table + 切分         │
│              │  run             │  run_experiment 入口        │
│              │  evaluate        │  precision / recall / F1   │
│              └───┬──────────┬───┘                            │
│                  │          │                                │
│       ┌──────────▼──┐  ┌───▼───────────┐                   │
│       │ algorithms/ │  │    viz/       │                   │
│       │  REGISTRY   │  │  timeseries   │                   │
│       │  base       │  │  Plotly HTML  │                   │
│       │ three_sigma │  └───────────────┘                   │
│       └──────┬──────┘                                       │
│              │                                              │
│        ┌─────▼──────┐                                       │
│        │   core/    │  稳定层（契约）                        │
│        │  Table     │  统一数据载体                          │
│        │  Algorithm │  三层协议                              │
│        │  Experiment│  Run / Result 模型                    │
│        │  Tracking  │  TrackingStore Protocol               │
│        │  Storage   │  ArtifactStore Protocol               │
│        └───────────┘                                       │
│                                                             │
│        ┌────────────┐                                       │
│        │  storage/  │  实现层                                │
│        │  sqlite    │  TrackingStore 实现                   │
│        │  fs        │  ArtifactStore 实现                   │
│        └───────────┘                                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘

依赖方向：CLI/UI → pipeline → algorithms + viz → core → storage
         pipeline → algorithms (经 REGISTRY，不直接 import)
         algorithms → core (仅消费/产出 Table)
         viz → core (消费 Table)
```

## 2. 数据流（run_experiment 全流程）

```text
CSV 文件
   │
   ▼ read_csv_to_table (字段推断)
Table (full) ──── schema 校验 (≥1 METRIC, ≤1 TIMESTAMP, ≤1 LABEL)
   │
   ▼ split_by_time (ratio=0.7)
Table (train)          Table (test)
   │                      │
   ▼ algo.fit()           ▼ algo.detect()
   │                      │
   │                 Table (detect result)
   │                      │
   │                      ▼ _validate_output (行数/timestamp/predicted_label)
   │                      │
   │                      ▼ evaluate (test_labels vs predicted_label → F1)
   │                      │
   └──────────────────────┼─────────────────────
                          │
                    ┌─────▼─────┐
                    │  落库      │  SQLite runs + metrics 表
                    │  持久化    │  FsArtifactStore → viz.html
                    └───────────┘
                          │
                    ┌─────▼─────┐
                    │ RunResult │  run_id / metrics / artifacts_path
                    └───────────┘
```

## 3. Table 贯穿示意

Table（DataFrame + TableSchema）是全链路唯一数据载体：

```text
┌─────────────────────────────────────────────────────────────────┐
│  Table = df: DataFrame + schema: TableSchema                    │
│  schema.roles: {"timestamp": TIMESTAMP, "value": METRIC,       │
│                 "is_anomaly": LABEL}                             │
│                                                                 │
│  CSV ──→ Table (输入) ──→ algo.fit(Table) ──→ None              │
│          Table (输入) ──→ algo.detect(Table) ──→ Table (输出)   │
│          Table (输入) ──→ evaluate ──→ metrics dict              │
│          Table (输出) ──→ viz.plot_timeseries ──→ HTML          │
│          Table (输出) ──→ UI 展示 / CLI 输出                    │
│                                                                 │
│  输出 Table 契约（AnomalyDetector）：                            │
│  ┌─ timestamp (TIMESTAMP) ─ 输入有则逐行带出                    │
│  ├─ <metric> (METRIC) ─ 原值保留                                │
│  ├─ <metric>.anomaly_score (METRIC)                              │
│  ├─ <metric>.threshold_upper/lower (METRIC)                      │
│  └─ predicted_label (LABEL) ─ 多指标 OR 合并                    │
└─────────────────────────────────────────────────────────────────┘
```

## 4. 稳定/可变分离

| 层 | 目录 | 性质 | 修改规则 |
|---|---|---|---|
| 稳定层 | `core/` | 契约（Protocol + 数据模型） | 修改需 ADR |
| 可变层 | `algorithms/` | 算法插件 | 注册即可接入 |
| 编排层 | `pipeline/` | 流程控制 | 经 REGISTRY 调用算法 |
| 表现层 | `cli/` `ui/` `viz/` | 交互与可视化 | 不写业务逻辑 |
| 实现层 | `storage/` | 存储实现 | 可替换（如迁移 MLflow） |

## 5. M0 关键文件清单

| 模块 | 文件 | 职责 |
|---|---|---|
| core | `table.py` | Table + TableSchema + FieldRole |
| core | `algorithm.py` | Algorithm Protocol + TaskType |
| core | `experiment.py` | ExperimentRun + RunResult + RunStatus |
| core | `tracking.py` | TrackingStore Protocol |
| core | `storage_iface.py` | ArtifactStore Protocol |
| core | `exceptions.py` | SchemaValidationError |
| algorithms | `base.py` | AnomalyDetector 子协议 |
| algorithms | `registry.py` | REGISTRY + @register |
| algorithms | `three_sigma.py` | 3-Sigma 实现 |
| pipeline | `preprocess.py` | read_csv_to_table + split_by_time |
| pipeline | `run.py` | run_experiment + 校验 |
| pipeline | `evaluate.py` | precision / recall / F1 |
| viz | `timeseries.py` | Plotly HTML 可视化 |
| storage | `sqlite_tracking.py` | SqliteTrackingStore |
| storage | `fs_artifact.py` | FsArtifactStore |
| storage | `schema.sql` | SQLite 表结构 |
| cli | `commands.py` | run / list-algos / list-runs |
| ui | `app.py` | Streamlit 三功能区 |
| smoke | `golden_data/metrics.csv` | 黄金数据集 |
| smoke | `test_e2e_smoke.py` | 参数化冒烟测试 |