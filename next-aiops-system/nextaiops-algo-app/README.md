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
企业 AIOps 团队中负责运维场景算法开发与效果验证的**算法工程师**——懂 Python/ML，长期被“数据分散、环境难装、实验难复现、上线交付慢”所困扰。

### 场景故事
面对“核心业务指标频繁抖动、告警不准”的需求，算法工程师在 NextAIOpsAlgoApp 上传历史指标数据、挑选若干异常检测算法、一键训练并可视化对比效果，最终将最优模型连同实验配置一键导出交付上线。

## 3. MVP 范围

以**指标异常检测**作为首个打通的算法能力，验证「数据 → 算法 → 实验」端到端闭环。

### 做什么
- **数据集管理**：CSV 上传、字段自动推断（timestamp / metric / label）、按时序切分
- **算法管理**：算法插件注册机制、版本与依赖、内置 3-Sigma
- **数据实验**：训练 / 评估 / 复现，落库 run_id / params / metrics / artifacts
- **结果可视化**：时间序列曲线 + 异常点标注 + 阈值线（Plotly HTML）
- **实验追踪**：SQLite + 文件系统轻量自研

### 不做什么（M0 范围外）
- 在线推理服务、多租户、权限/认证
- 流式数据接入（kafka/pulsar）
- AutoML、自动特征工程
- MLflow 接入（M1+ 评估）
- 多实体场景（KPI 多 ID）、窗口标签（NAB 风格）（M1+）

### 交互流程
1. 进入「数据集」 → 上传指标数据 CSV
2. 系统校验格式并推断字段角色 → 配置训练/测试切分比例 → 保存
3. 进入「算法」 → 选算法（默认 3-Sigma）→ 配置超参数
4. 进入「实验」 → 创建实验（绑定数据集 + 算法 + 参数）→ 提交训练
5. 查看实验状态与日志
6. 实验完成 → 查看评估报告（F1）+ 时间序列异常点可视化
7. 多实验横向对比 → 选定最优实验
8. 一键导出最优模型 + 实验配置

> M0 阶段交互通过 Streamlit 轻量看板实现；产品级前端交互留给后续迭代。

## 4. 快速开始

> ⏱️ 5 分钟跑通端到端实验

```bash
# 1. clone & 安装依赖
git clone <repo-url> && cd nextaiops-algo-app
pip install -e ".[dev]"

# 2. 跑一次冒烟实验（CLI）
python -m nextaiops_algo run --data tests/smoke/golden_data/metrics.csv --algo three_sigma

# 3. 启动可视化看板
streamlit run src/nextaiops_algo/ui/app.py
# 浏览器打开 http://localhost:8501
# 上传 tests/smoke/golden_data/metrics.csv → 选 three_sigma → 跑 → 看图
```

> 有 `make` 时可用 `make dev` / `make smoke ALG=three_sigma` / `make demo` 等简写。

## 5. 架构总览

```text
┌─────────────────────────────────────────────────────────────┐
│                    NextAIOpsAlgoApp M0                       │
│                                                             │
│  ┌─────────┐  ┌───────────┐  ┌───────────┐                │
│  │  CLI    │  │ Streamlit │  │  (REST)   │  ← M1+          │
│  └────┬────┘  └─────┬─────┘  └───────────┘                  │
│       └──────────────┼───────────────                       │
│                      │                                      │
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
│       │ three_sigma │  │  Plotly HTML  │                   │
│       └──────┬──────┘  └───────────────┘                   │
│              │                                              │
│        ┌─────▼──────┐                                       │
│        │   core/    │  稳定层（契约）                        │
│        │  Table     │  Algorithm  │  Experiment             │
│        └──────┬─────┘                                       │
│               │                                             │
│        ┌──────▼─────┐                                       │
│        │  storage/  │  实现层（SQLite + FS）                │
│        └────────────┘                                       │
└─────────────────────────────────────────────────────────────┘
```

**关键设计**：

- `core/` 是稳定层（契约），`algorithms/` 是可变层（插件），物理隔离
- 算法 I/O 统一为 `Table`（DataFrame + Schema），平台前置 schema 校验
- Pipeline 不感知具体算法，仅通过 REGISTRY 调用
- CLI / UI / viz 不写业务逻辑，只调 pipeline 与查询 storage

详见 [docs/architecture/M0-skeleton.md](docs/architecture/M0-skeleton.md)（数据流、Table 贯穿、稳定/可变分离）。

## 6. 项目状态

- **当前阶段**：M0（Walking Skeleton），见 [docs/PLAN.md](docs/PLAN.md)
- **路线图**：
  - **M0**：端到端最小闭环（3-Sigma + Streamlit demo）
  - **M1**：算法生态扩展（IsolationForest / LSTM-AE）+ 数据集版本化 + 多实验对比
  - **M2+**：MLflow 迁移、模型导出、AutoML 探索

## 7. 开发者指南

| 入口 | 用途 |
| --- | --- |
| [AGENTS.md](AGENTS.md) | AI 协作完整规约（必读） |
| [CLAUDE.md](CLAUDE.md) | Claude Code 会话入口 |
| [docs/PLAN.md](docs/PLAN.md) | M0 任务拆解（PR-1 ~ PR-6） |
| [docs/NextAIOpsSystem.md](docs/NextAIOpsSystem.md) | 系统总览与子系统关系 |
| [docs/adr/](docs/adr/) | 架构决策记录 |
| [changes/](changes/) | OpenSpec 风格变更提案（M1 启用） |
