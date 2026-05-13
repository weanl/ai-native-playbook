# M1 Batch — 批量实验架构补充

> M1 阶段新增模块关系、数据流与批量实验闭环示意。

## 1. 新增模块

| 模块 | 文件 | 职责 |
|---|---|---|
| pipeline | `batch.py` | `run_batch()` 批量引擎，顺序执行，per-algorithm error isolation |
| viz | `leaderboard.py` | `render_leaderboard()` 排行榜 DataFrame |
| viz | `overlay.py` | `render_overlay()` 时序叠加对比 Plotly Figure |
| viz | `heatmap.py` | `render_heatmap()` 算法×指标热力图 Plotly Figure |
| core | `experiment.py` | `BatchRun` / `BatchStatus` 数据模型 |
| storage | `schema.sql` | `batches` / `batch_runs` 表 |
| algorithms | `adapters/` | TSB-UAD 适配器 + 条件注册 |
| datasets | `registry.py` / `loaders.py` | 数据格式分发 + 内置数据集 |
| ui | `app.py` | Streamlit 三页面（单算法 / 批量 / 历史） |

## 2. 批量实验数据流

```text
数据源 (CSV/.out/npy/npz/builtin)
   │
   ▼ read_to_table (统一入口 + 后缀分发)
Table (full)
   │
   ▼ run_batch(dataset, algorithms="__all__")
   │
   ├─ for each algorithm:
   │   ├─ REGISTRY 查找 → run_experiment
   │   ├─ 异常 → FAILED ExperimentRun (不阻断)
   │   └─ 成功 → COMPLETED ExperimentRun
   │
   ▼ BatchRun (聚合)
   │
   ├─→ SqliteTrackingStore.log_batch (batches + batch_runs)
   │
   ├─→ render_leaderboard → DataFrame (PA-F1 排序)
   ├─→ render_overlay → Plotly Figure (N+1 subplot)
   ├─→ render_heatmap → Plotly Figure (RdYlGn)
   │
   └─→ CLI / UI 展示
```

## 3. TSB-UAD 桥接架构

```text
REGISTRY (基础: three_sigma, iqr)
   │
   ├─ [tsbuad] extras 安装?
   │   ├─ YES → adapters/tsbuad_registry.register_tsbuad()
   │   │         REGISTRY += iforest, lof, ocsvm, pca, hbos
   │   ├─ NO  → 不报错，仅含基础算法
   │
   ▼ TSBUADAdapter
   │  Table → ndarray → sliding window → model.fit → decision_scores_
   │  → align(scores, original_length) → threshold → predicted_label
   │  → Table (符合 AnomalyDetector 输出契约)
```

## 4. 可视化三件套

| 视图 | 输入 | 输出 | 用途 |
|---|---|---|---|
| 排行榜 | BatchRun + SqliteTrackingStore | DataFrame | 按 PA-F1 排序，FAILED 标 NaN |
| 时序叠加 | BatchRun + input Table | Plotly Figure | N+1 subplot 对比检测结果 |
| 热力图 | BatchRun + SqliteTrackingStore | Plotly Figure | 算法×指标矩阵，RdYlGn |

三个视图统一消费 `BatchRun`，不触碰算法实现或存储层内部。

## 5. UI 页面结构

```text
Streamlit app.py (sidebar 导航)
   ├─ 单算法实验 (上传 → 选算法 → 跑 → 看图)
   ├─ 批量实验 (上传 → 勾选算法 → 跑 → 3 tab: 排行榜/叠加/热力图)
   └─ 历史记录 (list_runs → 查看历史 viz)
```

侧边栏数据源选择器：上传 CSV / .out / npy/npz / 内置数据集。