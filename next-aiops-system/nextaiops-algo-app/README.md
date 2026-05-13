# NextAIOpsAlgoApp

> 下一代智能运维系统的算法平台子系统 — 智能大脑。

## 1. 项目定位

NextAIOpsAlgoApp 是 **NextAIOpsSystem** 的「算法平台」子系统，独立承载 AI 开发全流程能力，支撑算法的快速迭代与效果验证。

```text
                ┌──────────────────────────────────────┐
                │           NextAIOpsSystem            │
                │                                      │
监控采集 ──┐     │  ┌──────────────┐  ┌─────────────┐  │
日志/事件─┤────►│  │  运维智能体  │  │ 可视化门户  │  │
          │     │  └──────┬───────┘  └─────┬───────┘  │
          └────►│         ▼                ▼           │
                │  ┌──────────────────────────────┐   │
                │  │ ★ NextAIOpsAlgoApp（本仓库） │   │
                │  │   算法平台 / 智能大脑        │   │
                │  └──────────────────────────────┘   │
                └──────────────────────────────────────┘
```

子系统间解耦：算法平台与业务子系统完全解耦，可独立演进与部署。详见 [docs/NextAIOpsSystem.md](docs/NextAIOpsSystem.md)。

## 2. 目标用户与场景

### 典型用户画像
企业 AIOps 团队中负责运维场景算法开发与效果验证的**算法工程师**——懂 Python/ML，长期被"数据分散、环境难装、实验难复现、上线交付慢"所困扰。

### 场景故事
面对"核心业务指标频繁抖动、告警不准"的需求，算法工程师在 NextAIOpsAlgoApp 上传历史指标数据、挑选若干异常检测算法、一键训练并可视化对比效果，最终将最优模型连同实验配置一键导出交付上线。

## 3. 快速开始

> ⏱️ 5 分钟跑通端到端实验

### 安装

```bash
# 基础安装（2 个内置算法 + Streamlit UI）
git clone <repo-url> && cd nextaiops-algo-app
pip install -e ".[dev]"

# TSB-UAD 扩展安装（解锁 5 个额外算法）
pip install -e ".[dev,tsbuad]"
```

### 单次实验（CLI）

```bash
# 使用本地 CSV 文件
python -m nextaiops_algo run --data tests/smoke/golden_data/metrics.csv --algo three_sigma

# 使用内置数据集
python -m nextaiops_algo run --data yahoo_sample --algo iqr

# 传入超参数
python -m nextaiops_algo run --data yahoo_sample --algo three_sigma --params '{"k": 2}'
```

### 批量实验（CLI）

```bash
# 指定多个算法
python -m nextaiops_algo batch --data yahoo_sample --algos three_sigma,iqr

# 全部已注册算法
python -m nextaiops_algo batch --data tests/smoke/golden_data/metrics.csv --algos all

# 包含 TSB-UAD 算法（需安装 extras）
python -m nextaiops_algo batch --data yahoo_sample --algos three_sigma,iqr,iforest,pca,hbos
```

### 查询历史

```bash
python -m nextaiops_algo list-algos        # 列出所有已注册算法
python -m nextaiops_algo list-runs         # 查看实验记录
python -m nextaiops_algo list-batches      # 查看批量实验记录
```

### Streamlit 可视化看板

```bash
streamlit run src/nextaiops_algo/ui/app.py
# 浏览器打开 http://localhost:8501
```

看板包含三个页面：
- **单次实验**：上传数据 → 选算法 → 跑 → 看图
- **批量实验**：勾选多算法 → 一键跑 → 排行榜 + 时序对比 + 热力图
- **历史记录**：查看所有实验与批量实验结果

> 有 `make` 时可用 `make dev` / `make smoke` / `make demo` 等简写，详见 §7。

## 4. 数据输入

支持 5 种输入格式，由 `read_to_table()` 统一分发：

| 格式 | 示例 | 说明 |
|------|------|------|
| **CSV** | `metrics.csv` | 自动推断列角色（timestamp / metric / label） |
| **.out** | `data.out` | TSB-UAD 两列格式（value + label，无表头） |
| **npy** | `data.npy` + `label.npy` | NumPy 数组；单列 `(N,)` 或多列 `(N, features)` |
| **npz** | `data.npz` | 压缩数组；需含 `data` key，可选 `label` / `timestamp` |
| **内置数据集** | `yahoo_sample` | 3 个小型公开数据集，打包在 wheel 中 |

### 内置数据集

| 名称 | 点数 | 异常段 | 来源 |
|------|------|--------|------|
| `nab_sample` | 500 | 6 | NAB (Numenta Anomaly Benchmark) |
| `nasa_msl_sample` | 800 | 5 | NASA MSL (Mars Science Laboratory) |
| `yahoo_sample` | 1000 | 6 | Yahoo S5 A1Benchmark |

内置数据集可直接用名称引用，无需文件路径：

```bash
python -m nextaiops_algo run --data yahoo_sample --algo three_sigma
python -m nextaiops_algo batch --data nab_sample --algos three_sigma,iqr
```

### CSV 列角色推断

CSV 文件上传时自动推断列角色（大小写不敏感）：

| 角色 | 匹配关键词 | 数量约束 |
|------|-----------|---------|
| TIMESTAMP | timestamp, time, ts, datetime | ≤ 1 |
| LABEL | label, anomaly, is_anomaly, y | ≤ 1 |
| METRIC | 其他数值列 | ≥ 1 |

## 5. 算法库

### 内置算法（默认安装）

| 算法 | REGISTRY 名称 | 类型 | 说明 |
|------|---------------|------|------|
| 3-Sigma | `three_sigma` | 统计 | 均值 ± k·std 阈值，默认 k=3 |
| IQR | `iqr` | 统计 | Q1 − k·IQR / Q3 + k·IQR 阈值，默认 k=1.5 |

### TSB-UAD 算法（需 `pip install -e ".[tsbuad]"`）

| 算法 | REGISTRY 名称 | 类型 | 默认阈值策略 | 效果提示 |
|------|---------------|------|-------------|---------|
| IForest | `iforest` | ML / 树 | percentile 95 | 在短时序上可产生 F1 > 0 |
| LOF | `lof` | ML / 近邻 | sigma 3 | 短时序 F1 可能为 0 |
| OCSVM | `ocsvm` | ML / 边界 | sigma 3 | 短时序 F1 可能为 0 |
| PCA | `pca` | ML / 编码 | sigma 3 | 在短时序上可产生 F1 > 0 |
| HBOS | `hbos` | 统计 | percentile 97 | 在短时序上可产生 F1 > 0 |

> **LOF/OCSVM 效果说明**：这两个算法在默认参数和短时序（< 1500 点）上的异常检测能力有限，F1 可能为 0。这是算法本身在单变量短序列上的有效性限制，建议搭配不同数据集或调整阈值参数（如 `threshold_method: percentile`）使用。

### TSB-UAD 适配器架构

TSB-UAD 各算法的评分接口不一致，适配器采用 **per-model scoring hook** 模式：

- `iforest` / `ocsvm`: `model.detector_.decision_function(X_test)` → 取反
- `lof`: 直接创建 `sklearn.LocalOutlierFactor(novelty=True)` 评分
- `pca`: 手动计算重建误差（`scaler_` + `selected_components_`）
- `hbos`: 调用 `_calculate_outlier_scores(X_test)` → 取反求和

评分后经 **center-of-window 对齐** 将滑动窗口级别分数映射回点级别，再应用阈值策略生成 `predicted_label`。

## 6. 评估指标

每次实验返回 6 个指标：

| 指标 | 说明 |
|------|------|
| `precision` | TP / (TP + FP)，逐点计算 |
| `recall` | TP / (TP + FN)，逐点计算 |
| `f1` | 2·P·R / (P + R)，逐点 |
| `pa_precision` | Point-Adjust Precision，基于异常段调整 |
| `pa_recall` | Point-Adjust Recall，基于异常段调整 |
| `pa_f1` | Point-Adjust F1，排行榜默认排序指标 |

### Point-Adjust 规则

对每个连续异常段（ground truth label=1 的连续区间），只要预测命中其中任意一点，该整段所有点视为 TP；未命中的整段视为 FN；FP 保持逐点计算。PA-F1 通常高于标准 F1，更适合运维场景的"只要报了就行"评估逻辑。

## 7. 常用命令

| 命令 | 用途 |
|------|------|
| `make install` | 安装项目（开发模式） |
| `make test` | 运行所有测试 |
| `make lint` | 静态检查（ruff + mypy --strict） |
| `make fmt` | 格式化代码（ruff format） |
| `make smoke` | 冒烟测试（默认算法） |
| `make smoke ALG=three_sigma` | 指定算法冒烟测试 |
| `make smoke-tsbuad` | TSB-UAD 冒烟测试（需安装 extras） |
| `make demo` | 启动 Streamlit 看板 |
| `make setup` | 设置 git hooks（拦截 main 推送） |
| `make clean` | 清理缓存和临时文件 |

## 8. 架构总览

```text
┌─────────────────────────────────────────────────────────────┐
│                    NextAIOpsAlgoApp M1                       │
│                                                             │
│  ┌─────────┐  ┌───────────┐  ┌───────────┐                │
│  │  CLI    │  │ Streamlit │  │  (REST)   │  ← M2+          │
│  └────┬────┘  └─────┬─────┘  └───────────┘                  │
│       └──────────────┼───────────────                       │
│                      │                                      │
│              ┌───────▼──────────┐                            │
│              │    pipeline/     │  编排层                     │
│              │  preprocess      │  CSV/out/npy/npz → Table   │
│              │  run             │  run_experiment 入口        │
│              │  batch           │  run_batch 批量引擎         │
│              │  evaluate        │  precision/recall/F1/PA    │
│              └───┬──────────┬───┘                            │
│                  │          │                                │
│       ┌──────────▼──┐  ┌───▼───────────┐                   │
│       │ algorithms/ │  │    viz/       │                   │
│       │  REGISTRY   │  │  timeseries   │                   │
│       │ three_sigma │  │  leaderboard  │                   │
│       │ iqr         │  │  overlay      │                   │
│       │ TSB-UAD*    │  │  heatmap      │                   │
│       └──────┬──────┘  └───────────────┘                   │
│              │                                              │
│        ┌─────▼──────┐                                       │
│        │   core/    │  稳定层（契约）                        │
│        │  Table     │  Algorithm  │  Experiment             │
│        │  BatchRun  │  BatchStatus           │              │
│        └──────┬─────┘                                       │
│               │                                             │
│        ┌──────▼─────┐                                       │
│        │  storage/  │  实现层（SQLite + FS）                │
│        └────────────┘                                       │
└─────────────────────────────────────────────────────────────┘

* TSB-UAD 为 optional dependency，需 pip install -e ".[tsbuad]"
```

**关键设计**：

- `core/` 是稳定层（契约），`algorithms/` 是可变层（插件），物理隔离
- 算法 I/O 统一为 `Table`（DataFrame + Schema），平台前置 schema 校验
- Pipeline 不感知具体算法，仅通过 REGISTRY 调用
- CLI / UI / viz 不写业务逻辑，只调 pipeline 与查询 storage
- 批量实验引擎顺序执行，单算法失败不阻断整个 batch
- 三种可视化视图消费 BatchRun，不触碰算法实现

详见 [docs/architecture/M0-skeleton.md](docs/architecture/M0-skeleton.md)（数据流、Table 贯穿、稳定/可变分离）与 [docs/architecture/M1-batch.md](docs/architecture/M1-batch.md)（批量实验架构）。

## 9. 数据存储

实验结果自动落库，无需手动管理：

| 存储 | 位置 | 内容 |
|------|------|------|
| SQLite | `.nextaiops_algo/tracking.db` | runs / metrics / batches / batch_runs |
| 文件系统 | `.nextaiops_algo/runs/<run_id>/` | viz.html 等产物文件 |

可通过环境变量 `NEXTAIOPS_ALGO_HOME` 覆盖默认存储路径。

## 10. 项目状态

- **当前阶段**：M1（批量实验能力），见 [docs/PLAN.md](docs/PLAN.md)
- **M0 已完成**：端到端最小闭环（3-Sigma + IQR + Streamlit demo + CLI）
- **M1 已完成**：
  - 评估指标扩充（PA-F1 / PA-Precision / PA-Recall）
  - IQR 算法 + TSB-UAD 桥接层（5 算法 optional）
  - 数据输入多样化（CSV / .out / npy / npz / 内置数据集）
  - 批量实验引擎 + CLI batch/list-batches
  - 可视化三件套（排行榜 / 时序叠加对比 / 热力图）
  - Streamlit 批量实验页面
- **M2+**：MLflow 迁移、模型导出、AutoML 探索

## 11. 开发者指南

| 入口 | 用途 |
| --- | --- |
| [AGENTS.md](AGENTS.md) | AI 协作完整规约（必读） |
| [CLAUDE.md](CLAUDE.md) | Claude Code 会话入口 |
| [docs/PLAN.md](docs/PLAN.md) | M0 + M1 任务拆解（PR-1 ~ PR-7） |
| [docs/NextAIOpsSystem.md](docs/NextAIOpsSystem.md) | 系统总览与子系统关系 |
| [docs/adr/](docs/adr/) | 架构决策记录 |
| [changes/](changes/) | OpenSpec 风格变更提案（M1 启用） |