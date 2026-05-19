# docs/PLAN.md — M0 + M1 任务拆解（融合版）

> 本文件用于替换本地 `next-aiops-system/nextaiops-algo-app/docs/PLAN.md`。
> 融合原则：
> 1. M0 保留为 Walking Skeleton 基线，不改变已规划的 6 个 PR 的边界。
> 2. M1 在 M0 之后追加，围绕“多算法 × 单数据集批量实验 + 可视化对比”展开。
> 3. TSB-UAD 作为 M1 的 optional dependency 接入，不进入默认安装路径。
> 4. AI 启动每个 PR 时必须原文引用本 PR 的“范围”段落作为锚点。

---

# M0 任务拆解

> M0 阶段以 6 个 PR 完成 Walking Skeleton。
> AI 启动每个 PR 时必须原文引用本 PR 的“范围”段落作为锚点。

## M0 总验收线

打通端到端最小闭环：
**上传 CSV（单/多指标）→ 字段推断为 Table → 选算法（默认 3-Sigma）→ 训练 → 评估（F1）→ 出图（Plotly HTML）→ 落库（SQLite + 文件系统）**

完成标准：
- [ ] `make smoke` 全绿（参数化覆盖所有注册算法）
- [ ] `make demo` 启动 Streamlit，能完整走完 e2e
- [ ] CI（GitHub Actions）lint + type + unit + smoke 全绿
- [ ] 一次现场 demo 通过（人工 review）

> 前置：bootstrap 已落地 5 份“宪法 + 产品文档”：CLAUDE.md / AGENTS.md / README.md / docs/NextAIOpsSystem.md / docs/PLAN.md。

---

## PR-1：脚手架 + 工程基础设施

**目标**：建立项目骨架与工程基础设施，让后续 PR 有“地基”可踩。

**范围（仅修改/新增以下文件）**：
- `pyproject.toml`
- `Makefile`
- `Dockerfile` `docker-compose.yml`
- `.gitignore`
- `.github/workflows/nextaiops-algo.yml`（仓库根目录，monorepo CI 结构）
> **架构调整说明**：采用 monorepo 结构，CI workflow 放置在仓库根目录（`.github/workflows/`），通过 `paths` 过滤器触发子项目 CI，支持后续新增其他子系统。
- `src/nextaiops_algo/__init__.py`
- `src/nextaiops_algo/{core,algorithms,pipeline,viz,storage,cli,ui}/__init__.py`
- `tests/__init__.py` `tests/{unit,integration,smoke}/__init__.py`
- `changes/_template/{proposal.md,spec-diff.md,tasks.md}`
- `docs/adr/0000-template.md`
- `docs/TODO.md`（初始写入下述 M1+ 候选条目）

**`docs/TODO.md` 初始内容**：

```markdown
# M1+ 候选（M0 不做，避免遗忘）

- [ ] 支持 NAB 窗口标签（LABEL_WINDOW 角色或预处理转换器）
- [ ] 支持 KPI 多实体（ENTITY 角色 + 按实体 group-by 训练）
- [ ] 支持预切分模式（--split-mode=predefined）
- [ ] 支持按指标分别输出 predicted_label（predicted_label.<metric>）
- [ ] 支持按指标分别评估（F1.<metric>）
- [ ] 用户自定义 schema 覆盖（CSV 推断兜底）
- [ ] 评估命名空间包结构（共享 nextaiops 顶级命名空间）
```

**依赖声明**（写入 pyproject.toml）：
- 运行时：`numpy` `pandas` `scikit-learn` `plotly` `typer` `streamlit` `pydantic`
- 开发时：`pytest` `ruff` `mypy`

**验收线**：
- [ ] `make dev` 起容器成功
- [ ] `make test` 通过（即使是空测试占位）
- [ ] `make lint` 通过（ruff + mypy --strict 在 src/ 下）
- [ ] CI 在远端跑通（lint + test 两个 job）

**红线映射**：R6（不引入 PLAN 未列依赖），R7（不引入 MLflow / kafka / 认证库）

---

## PR-2：核心抽象（core/）

**目标**：定义稳定层契约——Table 数据载体、Algorithm 三层协议、实验/追踪/存储接口。`core/` 内**仅放抽象与数据模型，不含执行逻辑**。

**范围**：
- `src/nextaiops_algo/core/table.py`
  - `FieldRole`（StrEnum）：TIMESTAMP / METRIC / LABEL
  - `TableSchema`（pydantic）：`roles: dict[str, FieldRole]` + `columns_of(role)`
  - `Table`（pydantic）：`df: pd.DataFrame` + `schema: TableSchema`
    + 访问器：`timestamps() / metrics() / labels()`
    + 校验：至少 1 个 METRIC；最多 1 个 TIMESTAMP；最多 1 个 LABEL；roles 列名必须都在 df 中
- `src/nextaiops_algo/core/algorithm.py`
  - `TaskType`（StrEnum）：`ANOMALY_DETECTION`
  - `Algorithm`（Protocol，runtime_checkable）：`name` `task_type` `required_input_roles`
- `src/nextaiops_algo/core/experiment.py`：`ExperimentRun` `RunStatus` `RunResult` 数据模型
- `src/nextaiops_algo/core/tracking.py`：`TrackingStore` Protocol（log_run / get_run / list_runs）
- `src/nextaiops_algo/core/storage_iface.py`：`ArtifactStore` Protocol（put / get / path_for）
- `src/nextaiops_algo/core/exceptions.py`：异常基类 + `SchemaValidationError`
- 单测：
  - `tests/unit/test_table.py`
  - `tests/unit/test_table_schema.py`
  - `tests/unit/test_experiment.py`

**关键设计点**：
- 数据模型用 `pydantic.BaseModel`（含校验）
- 接口用 `typing.Protocol`（不强制继承）
- 实验“参数”用 `dict[str, Any]`，不在 core 锁死结构
- Table 通过访问器返回字段视图，不暴露内部 df 修改路径
- `metrics()` 返回 DataFrame（≥ 1 列），支持单/多指标
- `timestamps()` / `labels()` 返回 Series | None
- `Algorithm` 基础协议在 core 中只占位，具体子协议放 `algorithms/base.py`

**验收线**：
- [ ] 所有数据模型字段齐全且有校验
- [ ] 协议有完整 docstring 说明契约
- [ ] Table 不可变性测试通过（构造后修改 df 不污染原 Table）
- [ ] TableSchema 拒绝 roles 中出现 df 不存在的列名
- [ ] `columns_of(role)` 返回顺序稳定（按声明顺序）
- [ ] 无 METRIC 列的 Table 构造时抛 `SchemaValidationError`
- [ ] 多于 1 个 TIMESTAMP 或 LABEL 的 Table 构造时抛 `SchemaValidationError`
- [ ] 单 METRIC 与多 METRIC 的 Table 均能正确构造，`metrics()` 返回正确 DataFrame
- [ ] mypy --strict 通过

**红线映射**：R1（首次建立 core/，需在 PR 描述说明设计动机），R5（测试不允许吞异常）

---

## PR-3：存储层 + 算法插件机制

**目标**：实现 core/ 协议的轻量实现 + 建立算法插件注册机制 + 接入第一个算法（3-Sigma，支持单/多指标）。

**范围**：
- `src/nextaiops_algo/storage/sqlite_tracking.py`：`SqliteTrackingStore`
- `src/nextaiops_algo/storage/fs_artifact.py`：`FsArtifactStore`
- `src/nextaiops_algo/storage/schema.sql`：SQLite 表结构（runs + metrics）
- `src/nextaiops_algo/algorithms/base.py`：
  - `AnomalyDetector`（继承 `Algorithm`）任务子协议
  - 输出 Table 契约文档化（必选列 + 推荐列 + 对齐约束，见 AGENTS.md §9.3）
- `src/nextaiops_algo/algorithms/registry.py`：`REGISTRY` + `register` 装饰器
- `src/nextaiops_algo/algorithms/three_sigma.py`：第一个算法实现（Table I/O + 多指标支持）
- 单测：
  - `tests/unit/test_sqlite_tracking.py`
  - `tests/unit/test_fs_artifact.py`
  - `tests/unit/test_registry.py`
  - `tests/unit/test_three_sigma.py`

**关键设计点**：
- 默认存储路径 `./.nextaiops_algo/runs/<run_id>/`，可通过环境变量 `NEXTAIOPS_ALGO_HOME` 覆盖
- SQLite schema：
  - `runs(run_id PK, dataset_version, algorithm_name, params_json, status, artifacts_path, created_at)`
  - `metrics(run_id FK, metric_name, value)`
- AnomalyDetector 协议形态：

```python
class AnomalyDetector(Algorithm, Protocol):
    task_type            = TaskType.ANOMALY_DETECTION
    required_input_roles = {FieldRole.METRIC}
    def fit(self, data: Table) -> None: ...
    def detect(self, data: Table) -> Table: ...
```

- 3-Sigma 实现要求：
  - `fit`：对**每个** METRIC 列独立计算 mean / std / upper / lower，存为 `self._stats: dict[str, tuple[mean, std]]`
  - `detect` 输出 Table 结构：
    - `timestamp`（输入有则原样逐行带出；无则不输出）
    - 每个输入 METRIC 列的原值（列名与输入一致，角色 METRIC）
    - 每个 METRIC 列对应：
      - `<metric>.anomaly_score`（角色 METRIC）
      - `<metric>.threshold_upper` / `<metric>.threshold_lower`（角色 METRIC）
    - `predicted_label`（角色 LABEL，所有 METRIC 列异常标签 OR 合并）
  - 输出行数必须 == 输入行数

**验收线**：
- [ ] SqliteTrackingStore round-trip 一致（log_run → get_run 字段无损）
- [ ] FsArtifactStore 可 put / get 文件
- [ ] REGISTRY 至少含 `three_sigma`
- [ ] 3-Sigma 单 METRIC 输入：输出列含 `predicted_label` + `<metric>.anomaly_score` + `<metric>.threshold_upper` + `<metric>.threshold_lower` + 原 metric 列
- [ ] 3-Sigma 多 METRIC 输入（≥ 2 列）：每个 metric 都有对应 `.anomaly_score` / `.threshold_upper` / `.threshold_lower` 列；`predicted_label` 为 OR 合并（构造“仅第 1 列异常”输入，断言对应位置 predicted_label 为 1）
- [ ] 3-Sigma 输出行数 == 输入行数
- [ ] 输入有 timestamp 时输出原样逐行带出；输入无 timestamp 时输出也无 timestamp
- [ ] 3-Sigma 在已知小数据集上 F1 > 0（仅证明非退化实现）
- [ ] 所有输出列角色正确（score / threshold 均为 METRIC；predicted_label 为 LABEL）
- [ ] 单测全绿

**红线映射**：R2（算法仅消费/产出 Table，不接触存储；支持单/多指标；声明 required_input_roles），R3（log_run 必须含完整字段）

---

## PR-4：Pipeline 编排 + 可视化

**目标**：把 core + algorithms + storage 编排成 `run_experiment(...)` 一个函数，输出可视化 HTML。

**范围**：
- `src/nextaiops_algo/pipeline/preprocess.py`
  - `read_csv_to_table(path: Path) -> Table`：默认字段推断（按 AGENTS.md §9.4 规则）
  - `split_by_time(table: Table, ratio: float = 0.7) -> tuple[Table, Table]`：时序前后切分
- `src/nextaiops_algo/pipeline/run.py`
  - `run_experiment(dataset_path, algorithm_name, params, output_dir) -> RunResult`
  - 入口 `_validate_input(table, algo)`：fail-fast schema 校验
  - 出口 `_validate_output(input_table, result, algo)`：校验 AnomalyDetector 输出契约（必选列 + 行数 + timestamp 对齐）
- `src/nextaiops_algo/pipeline/evaluate.py`
  - `evaluate(input_table: Table, output_table: Table) -> dict`：返回 precision / recall / f1
- `src/nextaiops_algo/viz/timeseries.py`
  - 直接消费 detect 输出 Table
  - 多 METRIC 列 → 多 subplot（每个 metric 一个 subplot，各自含原线 + 上下阈值 + 异常点标记）
  - 优雅降级：缺 timestamp（用 index）/ 缺 threshold（不画阈值线）/ 缺 score（不画分值副图）
- 集成测试：`tests/integration/test_run_experiment.py`

**关键设计点**：
- `run_experiment` 流程：
  1. `read_csv_to_table` → `_validate_input`
  2. `split_by_time` → train / test
  3. `algo.fit(train)` → `algo.detect(test)` → `_validate_output(test, detect_result, algo)`
  4. `evaluate(test_input, detect_output)` → metrics
  5. 落库（runs + metrics 表）+ 持久化产物
  6. 调用 viz 出图
  7. 返回 RunResult
- pipeline/ **不准直接 import 具体算法实现**；只通过 REGISTRY 拿
- viz/ 输出纯 HTML 文件（Plotly），不依赖 web 框架
- evaluate 基于单 predicted_label 计算全局 F1（多指标拆分留 M1）

**验收线**：
- [ ] 集成测试：黄金数据（单 metric）+ 3-Sigma 跑通 run_experiment
- [ ] 集成测试：构造多 metric（≥ 2 列）输入 + 3-Sigma 跑通，`viz.html` 生成且文件 size > 0
- [ ] 断言 RunResult 字段齐全（含 run_id / metrics / artifacts_path）
- [ ] 断言 `viz.html` 存在且包含 plotly 标记字符串（如 `plotly-graph-div`）
- [ ] 断言已落库（SQLite 中查得到 run_id 及对应 metrics）
- [ ] 复现性：相同输入跑两次，metrics 完全一致
- [ ] schema 不合法时（如无 METRIC 列）提前抛 `SchemaValidationError`，不进算法
- [ ] `_validate_output` 单测：mock 算法返回行数不一致 → 抛 SchemaValidationError
- [ ] `_validate_output` 单测：mock 算法返回 timestamp 不对齐 → 抛 SchemaValidationError
- [ ] `_validate_output` 单测：mock 算法返回缺 predicted_label → 抛 SchemaValidationError

**红线映射**：R2（pipeline 经 REGISTRY 调用算法），R3（参数一致跑两次结果一致）

---

## PR-5：冒烟实验 + CLI

**目标**：建立“新算法接入即冒烟自动覆盖”的护栏；提供命令行入口。

**范围**：
- `tests/smoke/golden_data/metrics.csv`：黄金数据集
  - 对标 Yahoo S5 A1 格式：`timestamp,value,is_anomaly`
  - 行数 500~1500
  - 含明显异常点（数十个），异常比例约 3%~5%
- `tests/smoke/golden_data/README.md`：数据集说明（格式、行数、异常点位置、设计意图、来源对标）
- `tests/smoke/test_e2e_smoke.py`：参数化遍历 REGISTRY 所有算法
- `src/nextaiops_algo/cli/__main__.py`：`typer` 入口
- `src/nextaiops_algo/cli/commands.py`：
  - `run --data <csv> --algo <name> [--params <json>]`
  - `list-algos`
  - `list-runs [--limit N]`
- `Makefile` 增加 `smoke` 目标，支持 `make smoke ALG=<name>`
- `.github/workflows/ci.yml` 增加 smoke job

**关键设计点**：
- smoke 断言项：
  - 能跑通（无异常）
  - 产物齐全（viz.html 存在且 size > 0）
  - 落库成功（SQLite 可查到 run_id）
  - **非退化**（F1 > 0）
- smoke **不卡效果阈值**（如 F1 ≥ 0.8），效果基准属 M1 benchmark 范畴
- 黄金数据集为单 metric（多指标场景在 PR-3 / PR-4 单测中覆盖，smoke 保持最简）
- `make smoke ALG=three_sigma` 等价 `pytest tests/smoke -k three_sigma`
- CLI：`python -m nextaiops_algo run --data <csv> --algo <name>` 等价 `pipeline.run_experiment`

**验收线**：
- [ ] `make smoke` 全绿
- [ ] `make smoke ALG=three_sigma` 全绿
- [ ] CLI 跑通，输出 run_id 与 viz.html 路径
- [ ] `list-algos` 至少列出 `three_sigma`
- [ ] `list-runs` 能返回前一次 run 记录
- [ ] CI 远端 smoke job 通过

**红线映射**：R4（参数化覆盖所有注册算法 + 非退化断言），R5（smoke 断言不允许吞异常）

---

## PR-6：Streamlit 看板 + 收尾

**目标**：提供可视化交互 demo，写好架构图与产品入口文档，准备现场 demo。

**范围**：
- `src/nextaiops_algo/ui/app.py`：Streamlit 应用，三块功能区：
  - 上传数据（CSV 上传 + 字段推断结果展示：列名 → 角色映射）
  - 选算法 + 配参 + 跑实验（算法下拉来自 REGISTRY）
  - 看图 + 看历史 run 列表（可查看 metrics + 打开 viz.html）
- `Makefile` 增加 `demo` 目标（`streamlit run src/nextaiops_algo/ui/app.py`）
- `docs/architecture/M0-skeleton.md`：补充最终架构图（模块关系 + 数据流 + Table 贯穿示意）
- `README.md` 修订：
  - §4 快速开始：用实际跑通的命令更新（如确认 `make demo` 端口、黄金数据路径）
  - §5 架构总览：与 `docs/architecture/M0-skeleton.md` 保持一致（如有差异）
  - 其他章节不动
- 现场 demo 一次通过

**关键设计点**：
- Streamlit **不写业务逻辑**，只调用 `pipeline.run_experiment` 与查询 SQLite
- 算法下拉选项来自 REGISTRY 动态填充
- 字段推断结果展示：上传后显示 `column → role` 映射表，让用户验证（映射不正确时提示“M1 将支持手动覆盖”）
- 支持上传多指标 CSV（UI 展示多个 metric 的 subplot）

**验收线**：
- [ ] `make demo` 启动成功
- [ ] 上传黄金数据（单 metric）→ 选 3-Sigma → 跑 → 看图 → 看历史，全流程可视化
- [ ] 上传多指标 CSV → 字段推断映射表显示多个 METRIC 列 → 跑通 → 多 subplot 可见
- [ ] 字段推断映射在 UI 上可见
- [ ] README 步骤可被新人 5 分钟内复现
- [ ] M0 总验收线全部 ✅

**红线映射**：R6（UI 不直接读写 storage，只调 pipeline；README 修订严格限定在 §4 / §5）

---

## M0 依赖关系图

```text
PR-1 (脚手架)
   ↓
PR-2 (core 抽象：Table + Algorithm 三层协议)
   ↓
PR-3 (存储 + 算法插件 + 多指标 3-Sigma) ← 依赖 PR-2 协议
   ↓
PR-4 (pipeline + viz + 输出契约校验) ← 依赖 PR-3 实现
   ↓
PR-5 (smoke + cli)    ← 依赖 PR-4 的 run_experiment
   ↓
PR-6 (UI + 收尾)
```

线性推进，不并行。每个 PR 完成后人 review 通过再启动下一个。

---

## M0 → M1 候选 proposal（已融合进 M1）

| 原 ID | 标题 | M1 去向 |
| --- | --- | --- |
| 001 | 接入 IsolationForest | 纳入 M1 PR-3 TSB-UAD 桥接 |
| 002 | 接入 LSTM-AutoEncoder | 延后到 M2 深度学习算法桥接 |
| 003 | 数据集版本化与多策略切分（含预切分模式） | 部分纳入 M1 PR-4 数据输入多样化；完整版本化延后 |
| 004 | 多实验横向对比视图 | 纳入 M1 PR-5/PR-6/PR-7 |
| 005 | 模型 + 配置打包导出 | 延后到 M2 |
| 006 | 用户自定义 schema 覆盖（CSV 推断兜底） | 延后到 M2 或 M1 收尾候补 |
| 007 | 支持 ENTITY 角色（KPI 多实体场景） | 延后到 M2 |
| 008 | 支持 LABEL_WINDOW（NAB 窗口标签） | 延后到 M2 |
| 009 | 按指标分别输出与评估 | M1 暂只做全局多指标 OR；按指标拆分延后 |
| 010 | 迁移 MLflow（轻量自研→工业级） | 延后到 M2+ |
| 011 | 评估命名空间包结构（共享 nextaiops 顶级） | 多子系统出现时再做 |

---

# M1 任务拆解：可视化批量实验能力

> M1 阶段以 7 个 PR 完成“多算法 × 单数据集批量实验 + 可视化对比”能力。
> 对应 M0 → M1 候选 proposal 中的 #001、#004、#009（部分），并新增评估扩充、TSB-UAD 桥接、批量引擎、数据输入多样化。

## M1 总验收线

打通批量实验闭环：
**选定数据集 → 勾选多个算法 → 一键批量运行 → 排行榜 + 时序叠加对比 + 热力图 → 识别最优算法**

完成标准：
- [ ] 单数据集 × 5+ 算法批量实验一键跑通
- [ ] 排行榜表格（按 PA-F1 排序、条件着色）可见
- [ ] 时序曲线叠加对比图（多算法检测结果同图 + checkbox 切换）可见
- [ ] 热力图（算法 × 指标矩阵）可见
- [ ] 支持 CSV + TSB-UAD `.out` + npy/npz + 内置公开数据集四类输入
- [ ] `make smoke` 覆盖所有默认注册算法；`make smoke-tsbuad` 覆盖 optional TSB-UAD 算法
- [ ] CI 全绿；默认 CI 不强制安装 TSB-UAD 重依赖

---

## M1 调研结论：TSB-UAD 接入约束

**安装方式**：
- 推荐使用 PyPI 包作为 optional dependency：`TSB-UAD==0.0.3`
- README 同时出现 `pip install tsb-uad` 与 `pip install TSB-UAD`，pip 名称规范化后等价。
- 导入包名为 `TSB_UAD`。
- 不建议 git submodule / vendor 代码；只有当必须使用 NormA / Series2Graph 等未包含在 PyPI 包中的算法时，才考虑本地源码安装。

**依赖风险**：
- `TSB-UAD==0.0.3` 的 `setup.py` 依赖包括 `tensorflow>=2.13.0`、`tslearn`、`stumpy`、`tsfresh`、`arch`、`scikit-learn`、`networkx` 等。
- 因此 M1 必须将其放入 extras：`nextaiops-algo[tsbuad]`，避免污染基础环境和默认 CI。

**数据集约束**：
- TSB-UAD 的完整数据集不随 PyPI 包发布，README 说明因 GitHub 上传大小限制，数据集托管在外部下载。
- Public v2 提供 29 个数据集、3,427 条时间序列。
- TSB-UAD README 示例和公开 benchmark 常见格式是两列 `.out` 文件：第 1 列 value，第 2 列 label。
- 因此 M1 PR-4 不应把 `.npy` 称为 TSB-UAD 标准格式；应新增 `.out` loader，并保留 `.npy/.npz` 作为通用数组输入。

**首批算法约束**：
- TSB-UAD 文档明确列出 LOF、HBOS、OCSVM、Isolation Forest、PCA 等。
- 文档中未看到 KNN 作为 TSB-UAD 算法，因此 KNN 不纳入 M1 首批桥接。
- M1 首批桥接算法调整为：`iforest`、`lof`、`ocsvm`、`pca`、`hbos`。

**调研依据**：
- GitHub README: https://github.com/TheDatumOrg/TSB-UAD
- PyPI: https://pypi.org/project/TSB-UAD/
- ReadTheDocs algorithms: https://tsb-uad.readthedocs.io/en/latest/algorithms/index.html
- setup.py: https://raw.githubusercontent.com/TheDatumOrg/TSB-UAD/main/setup.py

---

## PR-1（M1）：评估指标扩充

**目标**：从单一 F1 扩展到 Precision / Recall / F1 + Point-Adjust 系列，为批量对比提供多维评估基础。

**范围**：
- `src/nextaiops_algo/pipeline/evaluate.py` ← 重构扩展
- `src/nextaiops_algo/core/experiment.py` ← 确认 RunResult.metrics 类型兼容
- `tests/unit/test_evaluate.py` ← 扩展
- `tests/unit/test_evaluate_pa.py` ← 新增
- `docs/adr/0001-point-adjust-evaluation.md` ← 新增 ADR

**具体内容**：

| 指标 | 说明 | 实现要求 |
|------|------|----------|
| Precision | TP / (TP + FP) | 与 sklearn 一致 |
| Recall | TP / (TP + FN) | 与 sklearn 一致 |
| F1 | 2PR/(P+R) | 保持兼容 |
| PA-Precision | Point-Adjust Precision | 基于调整后标签 |
| PA-Recall | Point-Adjust Recall | 基于调整后标签 |
| PA-F1 | Point-Adjust F1 | 排行榜默认排序指标 |

**Point-Adjust 逻辑**：
- 对每个连续异常段（ground truth label=1 的连续区间），只要预测命中其中任意一点，该整段所有点视为 TP。
- 未被命中的整段所有点视为 FN。
- FP 保持逐点计算。
- 推荐实现独立函数：`point_adjust_labels(y_true, y_pred) -> np.ndarray`，再套标准 precision / recall / f1 计算。

**关键设计点**：
- `evaluate()` 返回值仍为 `dict[str, float]`，key 扩展为：
  - `precision`
  - `recall`
  - `f1`
  - `pa_precision`
  - `pa_recall`
  - `pa_f1`
- `RunResult.metrics` 保持 `dict[str, float]`，无需改结构。
- 空输入必须 fail-fast，不返回静默 0。
- 无 LABEL 或无 `predicted_label` 时抛 `SchemaValidationError`。
- `zero_division=0`，保证全 0 预测边界稳定。

**验收线**：
- [ ] 标准 Precision / Recall / F1 与 sklearn 结果一致（构造已知输入断言）
- [ ] PA-F1 在“命中异常段任意一点”场景下 > 标准 F1（构造用例证明）
- [ ] 全 0 预测、全 1 预测、空输入边界测试通过
- [ ] 缺 label / 缺 predicted_label 时提前抛异常
- [ ] `run_experiment` 输出的 metrics 包含 6 个 key
- [ ] 既有 smoke 测试仍然全绿（兼容）

**红线映射**：R1（修改 core/ 的 metrics 语义，需在 PR 描述记录 ADR）

---

## PR-2（M1）：IQR 算法

**目标**：新增第二个自研统计型算法，验证插件机制的可扩展性。

**范围**：
- `src/nextaiops_algo/algorithms/iqr.py`
- `tests/unit/test_iqr.py`
- `tests/smoke/test_e2e_smoke.py` ← 参数化自动覆盖（无需手动新增）

**IQR 算法设计**：
- `fit()`：对每个 METRIC 列计算 Q1、Q3、IQR = Q3 - Q1。
- `detect()`：
  - `anomaly_score` = 距离 `[Q1 - k*IQR, Q3 + k*IQR]` 的归一化距离。
  - `threshold_upper` = Q3 + k * IQR。
  - `threshold_lower` = Q1 - k * IQR。
  - `predicted_label` = 超出阈值为 1，多 metric OR 合并。
- 超参：`k`（默认 1.5）。
- 输出 Table 结构与 3-Sigma 完全一致。

**关键设计点**：
- 当 IQR=0 时，使用安全分母或退化策略，避免除零。
- 多 METRIC 输出必须逐列包含：
  - `<metric>.anomaly_score`
  - `<metric>.threshold_upper`
  - `<metric>.threshold_lower`
- `REGISTRY` 名称为 `iqr`。
- `fit()` 不接触存储，`detect()` 只消费/产出 Table。

**验收线**：
- [ ] `REGISTRY` 含 `iqr`
- [ ] 单/多 METRIC 输入输出结构正确
- [ ] 输出行数 == 输入行数
- [ ] 在黄金数据集上 F1 > 0（非退化）
- [ ] `make smoke ALG=iqr` 全绿

**红线映射**：R2（算法仅消费/产出 Table，不接触存储）

---

## PR-3（M1）：TSB-UAD 算法桥接层

**目标**：通过 Adapter 模式桥接 TSB-UAD 已有算法实现，快速扩充算法库到 5+ 个，同时保持默认安装轻量。

**范围**：
- `src/nextaiops_algo/algorithms/adapters/__init__.py`
- `src/nextaiops_algo/algorithms/adapters/tsbuad_adapter.py` ← 通用适配器
- `src/nextaiops_algo/algorithms/adapters/tsbuad_configs.py` ← 各算法默认参数
- `src/nextaiops_algo/algorithms/adapters/tsbuad_registry.py` ← optional 注册入口
- `tests/unit/test_tsbuad_adapter.py`
- `tests/unit/test_tsbuad_import_guard.py`
- `tests/smoke/test_tsbuad_smoke.py`
- `pyproject.toml` ← 新增 optional dependency group `[tsbuad]`
- `Makefile` ← 新增 `smoke-tsbuad`

**依赖声明**：

```toml
[project.optional-dependencies]
tsbuad = [
  "TSB-UAD==0.0.3",
]
```

**首批桥接算法**：

| 算法 | TSB-UAD 类 | 类型 | M1 状态 |
| ---- | ---------- | ---- | ------- |
| IsolationForest | `IForest` | ML / tree | 纳入 |
| LOF | `LOF` | ML / proximity | 纳入 |
| OCSVM | `OCSVM` | ML / boundary | 纳入，允许单独适配 |
| PCA | `PCA` | ML / encoding | 纳入 |
| HBOS | `HBOS` | statistical | 纳入 |
| KNN | 未在 TSB-UAD 文档首批算法中确认 | 暂不纳入 M1 |

**桥接架构**：

```python
class TSBUADAdapter:
    """将 TSB-UAD 算法包装为 AnomalyDetector 协议。"""

    def __init__(
        self,
        algo_class: type,
        default_params: dict[str, object],
        threshold_method: str = "sigma",
    ) -> None:
        ...

    def fit(self, data: Table) -> None:
        # Table → metric ndarray
        # 单变量默认走 sliding window
        # 多变量先进入 M1 降级策略：逐 metric 打分后 max/OR 合并，避免误用 univariate 模型
        ...

    def detect(self, data: Table) -> Table:
        # score → threshold → predicted_label
        # 输出契约对齐 AnomalyDetector
        ...
```

**输入转换策略**：
- TSB-UAD 是 univariate benchmark。M1 不假设其所有算法原生支持多变量。
- 单 METRIC：
  1. `series = table.metrics().iloc[:, 0].to_numpy(dtype=float)`
  2. `window = find_length(series)` 或配置固定窗口
  3. `X = Window(window=window).convert(series)`
  4. `model.fit(X)`
  5. 读取 `decision_scores_`
  6. 将 window-level score 对齐回原始长度
- 多 METRIC：
  - M1 默认逐 metric 独立运行 TSB-UAD 模型。
  - 每列生成 score，再用 `max(score)` 合并为全局 `predicted_label`。
  - 完整 multivariate bridge 延后到 M2。

**阈值策略**：
- 默认：`mean(scores) + 3 * std(scores)`。
- 可配置：`threshold_method` 支持：
  - `sigma`
  - `percentile`
  - `fixed`
- 参数示例：

```json
{
  "threshold_method": "percentile",
  "threshold_percentile": 98
}
```

**注册策略**：
- 未安装 TSB-UAD 时，不注册 `iforest` / `lof` / `ocsvm` / `pca` / `hbos`，且不报错。
- 安装 `nextaiops-algo[tsbuad]` 后，动态注册上述算法。
- `make smoke` 默认只覆盖基础算法：`three_sigma`、`iqr`。
- `make smoke-tsbuad` 在显式安装 extras 后覆盖 TSB-UAD 算法。

**关键设计点**：
- adapter 层负责 Table ↔ numpy 转换，TSB-UAD 源码零修改。
- 不直接依赖 TSB-UAD 自带 `predict()` 作为唯一出口；优先读取 `decision_scores_` 并用项目内阈值策略生成 `predicted_label`。
- 所有输出必须通过 M0 的 `_validate_output`。
- OCSVM 如果接口与其他类不一致，允许在 adapter 中做 per-class hook。
- 不把 TensorFlow 相关算法（LSTM / CNN / AE）纳入 M1，以控制复杂度与 CI 风险。

**验收线**：
- [ ] 未安装 `[tsbuad]` 时 `REGISTRY` 仅含基础算法，无 ImportError
- [ ] 安装 `[tsbuad]` 后 `REGISTRY` 含 `iforest` `lof` `ocsvm` `pca` `hbos`
- [ ] 每个桥接算法在黄金数据集上 F1 > 0 或 PA-F1 > 0（非退化）
- [ ] 输出 Table 结构符合 AnomalyDetector 输出契约
- [ ] `make smoke` 全绿（基础算法）
- [ ] `make smoke-tsbuad` 全绿（显式安装 extras 后）
- [ ] 默认 CI 不因 TSB-UAD 依赖失败而失败；可选 CI job 可单独覆盖 extras

**红线映射**：R1（新增 adapter 模式需 ADR），R6（重依赖必须 optional）

---

## PR-4（M1）：数据输入多样化

**目标**：支持 CSV / TSB-UAD `.out` / npy/npz / 内置公开数据集四类输入方式，为批量实验提供丰富数据源。

**范围**：
- `src/nextaiops_algo/pipeline/preprocess.py` ← 扩展统一入口
- `src/nextaiops_algo/datasets/__init__.py`
- `src/nextaiops_algo/datasets/registry.py` ← 数据集注册表
- `src/nextaiops_algo/datasets/loaders.py` ← 各格式 loader
- `src/nextaiops_algo/datasets/builtin/` ← 内置小型数据集（单个文件 < 1MB）
- `tests/unit/test_loaders.py`
- `tests/unit/test_builtin_datasets.py`

**支持的输入格式**：

| 格式 | 说明 | 加载方式 |
| ---- | ---- | -------- |
| CSV | M0 已有格式 | `read_csv_to_table(path)` |
| `.out` | TSB-UAD 常见两列格式：value + label | `read_tsbuad_out_to_table(path)` |
| npy | 通用数组格式 | `read_npy_to_table(data_path, label_path=None)` |
| npz | 通用压缩数组格式 | `read_npz_to_table(path)` |
| 内置数据集 | wheel 内打包的小型公开样例 | `load_builtin(name)` |

**TSB-UAD `.out` loader 约定**：
- 默认读取无表头两列：
  - 第 1 列：`value`
  - 第 2 列：`is_anomaly`
- 输出 Table：
  - `value` → METRIC
  - `is_anomaly` → LABEL
- 无 timestamp，后续 viz 使用 index。
- 若发现列数不是 2，抛友好错误，提示使用 CSV loader 或显式 schema。

**npy/npz 格式适配**：
- `data.npy`：shape `(N,)` 或 `(N, features)`。
- `label.npy`：shape `(N,)`，可选。
- 多 feature 列自动命名：
  - `metric_0`
  - `metric_1`
  - ...
- 无 timestamp → Table 中不设 TIMESTAMP 角色。
- npz 推荐 key：
  - `data`
  - `label`
  - `timestamp`（可选）

**内置数据集建议**：
- `yahoo_sample`
- `nab_sample`
- `nasa_msl_sample`

每个内置数据集附 metadata：

```python
{
    "name": "yahoo_sample",
    "source": "TSB-UAD Public / Yahoo",
    "n_points": 1500,
    "n_anomalies": 6,
    "description": "Small Yahoo-like univariate time series for smoke and UI demo.",
}
```

**关键设计点**：
- 新增统一入口：`read_to_table(path_or_name: str | Path) -> Table`
- 分发顺序：
  1. 若命中 builtin registry → `load_builtin(name)`
  2. 后缀 `.csv` → CSV
  3. 后缀 `.out` → TSB-UAD out
  4. 后缀 `.npy` / `.npz` → 数组 loader
  5. 其他 → 抛友好错误
- 内置数据集打包在 wheel 中，不依赖运行时网络下载。
- `datasets/registry.py` 与 `algorithms/registry.py` 设计风格一致。
- 不在 M1 自动下载完整 TSB-UAD 数据集；下载脚本可作为后续 M2 能力。

**验收线**：
- [ ] CSV 输入兼容 M0 行为，无回归
- [ ] `.out` 输入可加载 TSB-UAD 两列数据并构造正确 Table
- [ ] npy/npz 输入可构造正确 Table
- [ ] 内置数据集：`list_builtin()` 返回 ≥ 3 个名称，`load_builtin()` 返回有效 Table
- [ ] `read_to_table` 可根据后缀 / 名称自动分发
- [ ] 所有 loader 对空文件、格式错误、长度不一致有友好错误提示
- [ ] 内置数据集单文件均 < 1MB

**红线映射**：R6（不引入未列依赖；内置数据不可膨胀 wheel）

---

## PR-5（M1）：批量实验引擎

**目标**：核心能力——一次提交多算法 × 单数据集的矩阵实验，统一管理结果。

**范围**：
- `src/nextaiops_algo/pipeline/batch.py` ← 新增
- `src/nextaiops_algo/core/experiment.py` ← 新增 BatchRun / BatchStatus 模型
- `src/nextaiops_algo/storage/sqlite_tracking.py` ← 扩展 batch 表
- `src/nextaiops_algo/storage/schema.sql` ← 新增 batches / batch_runs
- `src/nextaiops_algo/cli/commands.py` ← 新增 batch / list-batches 命令
- `tests/unit/test_batch.py`
- `tests/integration/test_batch_e2e.py`

**BatchRun 数据模型**：

```python
class BatchRun(BaseModel):
    batch_id: str
    dataset_source: str
    algorithm_names: list[str]
    created_at: datetime
    runs: list[ExperimentRun]
    status: BatchStatus  # PENDING / RUNNING / COMPLETED / PARTIAL_FAILED / FAILED
```

**批量引擎 API**：

```python
def run_batch(
    dataset: str | Path,
    algorithms: list[str] | Literal["__all__"],
    params_override: dict[str, dict[str, object]] | None = None,
    output_dir: Path | None = None,
) -> BatchRun:
    ...
```

**执行策略**：
- M1 阶段顺序执行（for 循环），不引入并行。
- 单个算法失败不阻断整个 batch：
  - 捕获异常
  - 标记该 run 为 FAILED
  - 记录 error message
  - 继续下一个算法
- 执行过程打印进度：
  - `[2/7] Running iqr...`
- `__all__` 只表示当前已注册算法：
  - 未安装 TSB-UAD 时只跑基础算法
  - 安装 extras 后包含 TSB-UAD 算法

**CLI 扩展**：

```bash
python -m nextaiops_algo batch \
  --data tests/smoke/golden_data/metrics.csv \
  --algos three_sigma,iqr,iforest,lof \
  --output ./.nextaiops_algo/batch_results/
```

```bash
python -m nextaiops_algo list-batches --limit 20
```

**SQLite schema 建议**：

```sql
CREATE TABLE IF NOT EXISTS batches (
  batch_id TEXT PRIMARY KEY,
  dataset_source TEXT NOT NULL,
  algorithm_names_json TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS batch_runs (
  batch_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  algorithm_name TEXT NOT NULL,
  status TEXT NOT NULL,
  error_message TEXT,
  PRIMARY KEY (batch_id, run_id),
  FOREIGN KEY (batch_id) REFERENCES batches(batch_id),
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
```

**验收线**：
- [ ] `run_batch` 5 个算法 × 黄金数据集 一次跑通
- [ ] 返回 BatchRun 含每个算法对应 ExperimentRun
- [ ] 每个成功 run 有完整 metrics
- [ ] 某算法故意传错参数 → 该 run FAILED，其余 COMPLETED
- [ ] batch_id 可查询（`list-batches` CLI 命令）
- [ ] SQLite 中 batch 表记录正确
- [ ] `make smoke` 仍全绿

**红线映射**：R3（追踪字段完整），R5（失败不能吞异常）

---

## PR-6（M1）：可视化三件套

**目标**：M1 核心交付物——三种批量实验可视化视图。

**范围**：
- `src/nextaiops_algo/viz/leaderboard.py` ← 排行榜
- `src/nextaiops_algo/viz/overlay.py` ← 时序叠加对比
- `src/nextaiops_algo/viz/heatmap.py` ← 热力图
- `tests/unit/test_viz_leaderboard.py`
- `tests/unit/test_viz_overlay.py`
- `tests/unit/test_viz_heatmap.py`

### 视图 ① 排行榜表格

```text
输入：BatchRun
输出：Pandas DataFrame（可直接用于 Streamlit st.dataframe）

列：
Algorithm
Status
F1
PA-F1
Precision
Recall
PA-Precision
PA-Recall
Error

排序：默认按 PA-F1 降序
样式：最优值加粗/高亮色，FAILED 行置灰
```

**函数签名**：

```python
def render_leaderboard(
    batch_run: BatchRun,
    sort_by: str = "pa_f1",
) -> pd.DataFrame:
    ...
```

### 视图 ② 时序曲线叠加对比

```text
输入：BatchRun + 原始数据 Table
输出：Plotly Figure（HTML）

布局：
- 顶部：原始时序曲线 + Ground Truth 异常区间（灰色背景带）
- 下方每个算法一行子图：
  - 原始曲线（浅色）
  - 该算法的 predicted_label 异常点（红色标记）
  - threshold 线（虚线，如该算法输出 threshold）
- 共享 X 轴（时间/索引）
- 顶部提供 checkbox / legend 控制显示哪些算法行

降级：
- 无 timestamp → 用 index
- 算法 FAILED → 该行显示 “FAILED” 注释
- 多 METRIC → M1 默认展示第一个 metric；后续 M2 支持 metric selector
```

**函数签名**：

```python
def render_overlay(
    batch_run: BatchRun,
    input_table: Table,
    metric_name: str | None = None,
) -> plotly.graph_objects.Figure:
    ...
```

### 视图 ③ 热力图（算法 × 指标矩阵）

```text
输入：BatchRun
输出：Plotly Figure（HTML）

布局：
- X 轴：指标名（F1, PA-F1, Precision, Recall, ...）
- Y 轴：算法名
- 颜色：数值越高越深绿，越低越深红
- 每个格子显示数值（保留 2 位小数）
- 色阶：RdYlGn
- FAILED 算法显示 NaN / 灰色
```

**函数签名**：

```python
def render_heatmap(
    batch_run: BatchRun,
    metrics: list[str] | None = None,
) -> plotly.graph_objects.Figure:
    ...
```

**关键设计点**：
- 三个视图函数签名统一消费 `BatchRun`，不触碰 storage。
- Plotly Figure 可 `.to_html()` 存为 artifact，也可直接传给 Streamlit `st.plotly_chart()`。
- viz 层不重新计算指标，只消费 batch 结果。
- 排行榜列名展示可用 UI 友好名，但底层 metrics key 维持 snake_case。

**验收线**：
- [ ] 排行榜：5 算法 BatchRun → 表格行数 = 5，按 PA-F1 排序正确
- [ ] 时序叠加：生成 HTML，含 N+1 个 subplot（1 原始 + N 算法）
- [ ] 热力图：颜色映射正确（构造已知数据断言最大值对应最高值）
- [ ] FAILED 算法在排行榜中标灰、在时序图中显示 FAILED
- [ ] 所有 HTML artifact 文件 size > 0 且含 `plotly` 标记

**红线映射**：R2（viz 只消费 Table/Run，不接触算法实现），R5（测试不吞异常）

---

## PR-7（M1）：UI 整合 + 收尾

**目标**：将批量实验能力集成到 Streamlit UI，更新文档，完成 M1 交付。

**范围**：
- `src/nextaiops_algo/ui/app.py` ← 重构，新增批量实验入口
- `src/nextaiops_algo/ui/pages/batch_experiment.py` ← 新页面
- `src/nextaiops_algo/cli/commands.py` ← 补充 `batch` / `list-batches` 命令说明
- `docs/PLAN.md` ← 更新 M0 验收 checkbox 为已完成 + M1 验收线
- `docs/architecture/M1-batch.md` ← M1 架构补充文档
- `docs/adr/0001-point-adjust-evaluation.md`
- `docs/adr/0002-tsbuad-bridge-pattern.md`
- `README.md` ← 更新快速开始 + 项目状态
- `Makefile` ← 如需要，新增 `demo-batch` 或复用 `make demo`

**Streamlit 批量实验页面交互流**：
1. 选择数据源：
   - 上传 CSV
   - 上传 TSB-UAD `.out`
   - 上传 npy/npz
   - 选择内置数据集
2. 勾选算法：
   - checkbox 列表来自 REGISTRY
   - 支持“全选”
   - 未安装 TSB-UAD 时显示提示：“安装 nextaiops-algo[tsbuad] 可解锁更多算法”
3. 点击「开始批量实验」→ 显示进度条。
4. 完成后切换 Tab：
   - Tab 1：排行榜表格（可点击列头排序）
   - Tab 2：时序叠加对比图
   - Tab 3：热力图
5. 支持查看历史 Batch：
   - 侧边栏下拉选择 batch_id
   - 重新加载排行榜与图表

**README 更新要求**：
- 增加基础安装：

```bash
pip install -e ".[dev]"
```

- 增加 TSB-UAD optional 安装：

```bash
pip install -e ".[dev,tsbuad]"
```

- 增加批量实验 CLI 示例：

```bash
python -m nextaiops_algo batch \
  --data yahoo_sample \
  --algos three_sigma,iqr,iforest,lof
```

- 增加 UI 示例：

```bash
make demo
```

**ADR 要求**：
- `docs/adr/0001-point-adjust-evaluation.md`
  - 为什么新增 PA 指标
  - 与标准 F1 的差异
  - 边界行为
- `docs/adr/0002-tsbuad-bridge-pattern.md`
  - 为什么 TSB-UAD 作为 optional dependency
  - 为什么用 Adapter 而不是 vendor
  - 为什么 M1 不纳入深度学习算法
  - 为什么 KNN 暂不纳入 TSB-UAD 首批桥接

**验收线**：
- [ ] Streamlit 批量实验页面完整走通
- [ ] 三种视图均可在 UI 中交互展示
- [ ] 内置数据集可在 UI 中直接选择使用
- [ ] CLI `batch` 命令与 UI 功能对等
- [ ] ADR 文档已撰写（至少 2 篇）
- [ ] README 更新反映 M1 能力
- [ ] M1 总验收线全部 ✅

**红线映射**：R6（UI 不写业务逻辑，只调用 pipeline/viz/storage 查询接口）

---

## M1 依赖关系图

```text
PR-1 (评估指标扩充)
   ↓
PR-2 (IQR 算法) ─────────────┐
   ↓                          │
PR-3 (TSB-UAD 桥接) ─────────┤
   ↓                          │
PR-4 (数据输入多样化) ────────┤
                              ↓
                    PR-5 (批量实验引擎) ← 依赖 PR-1~4
                              ↓
                    PR-6 (可视化三件套) ← 依赖 PR-5
                              ↓
                    PR-7 (UI 整合 + 收尾) ← 依赖 PR-6
```

PR-1 为前置（评估指标被后续所有 PR 使用）。
PR-2 / PR-3 / PR-4 可并行开发（都依赖 PR-1，但彼此无强依赖）。
PR-5 → PR-6 → PR-7 线性推进。

---

## M1 实施顺序建议

### 推荐分支策略

```bash
git checkout -b docs/merge-m1-plan
```

完成 PLAN 更新后合并文档分支，再按 PR 顺序创建实现分支：

```bash
git checkout -b feat/m1-pr1-evaluation-metrics
git checkout -b feat/m1-pr2-iqr
git checkout -b feat/m1-pr3-tsbuad-adapter
git checkout -b feat/m1-pr4-datasets
git checkout -b feat/m1-pr5-batch-engine
git checkout -b feat/m1-pr6-batch-viz
git checkout -b feat/m1-pr7-ui-integration
```

### 每个 PR 启动前

AI 或开发者必须先在 PR 描述中原文引用对应 PR 的“范围”段落，作为 scope anchor。

### 每个 PR 合并前

至少执行：

```bash
make lint
make test
make smoke
```

如果 PR-3 或后续涉及 TSB-UAD extras：

```bash
pip install -e ".[dev,tsbuad]"
make smoke-tsbuad
```

### 建议的落地节奏

1. 先合并本 PLAN 文件。
2. 完成 M0，如果 M0 尚未全部通过，不进入 M1 实现。
3. M1 PR-1 先做评估指标扩充。
4. M1 PR-2 / PR-3 / PR-4 可并行，但推荐顺序为：
   - PR-2 IQR：快速扩充基础算法，风险最低。
   - PR-4 数据输入：先稳定 loader。
   - PR-3 TSB-UAD：重依赖和接口风险较高，最后做。
5. PR-5 开始批量引擎。
6. PR-6 可视化三件套。
7. PR-7 UI + README + ADR 收尾。

---

# M1.5 任务拆解：单算法实验工作台增强

> M1.5 聚焦“单算法实验”从 demo 形态升级为可解释、可调参、可预览的实验工作台。
> 本阶段不改变 `core/` 既有接口，不引入新重依赖；优先复用现有 Table / pipeline / viz / storage 边界。

## M1.5 总验收线

打通增强后的单算法实验闭环：
**选择或上传数据 → 数据画像与曲线预览 → 选择算法并理解参数 → 运行实验 → 结果数量解释 + GT/TP/FP/FN 可视化 → 历史可追溯**

完成标准：
- [ ] 单算法页能在运行前展示字段推断、指标曲线、真实异常标签与数据特征
- [ ] 算法参数以表单展示默认值、类型、含义与建议，不再要求用户手写 JSON
- [ ] 用户配置的参数真实参与算法实例化、落库，并参与实验标识生成
- [ ] 实验结果表格展示真实异常数、算法检出数、TP / FP / FN / TN、异常段命中情况
- [ ] 结果曲线叠加真实异常标签，并区分命中、误报、漏检
- [ ] 图表交互主要依赖 hover / legend / zoom / pan / double-click reset 等鼠标操作
- [ ] 支持多文件或 zip 作为同一数据集的方案完成设计，代码落地后保持 schema 一致性校验

## PR-1（M1.5）：算法参数元信息 + 参数生效链路

**目标**：让单算法实验的参数配置从“手写 JSON 且不一定生效”升级为“算法声明参数元信息，UI 表单引导配置，pipeline 使用参数创建算法实例”。

**范围**：
- `src/nextaiops_algo/algorithms/params.py`：新增参数元信息模型（名称、类型、默认值、说明、取值范围、枚举、是否参与实验标识）
- `src/nextaiops_algo/algorithms/registry.py`：新增按参数创建算法实例的 helper，例如 `create_algorithm(name, params)`
- `src/nextaiops_algo/algorithms/three_sigma.py`：支持 `k` 参数，默认 `3.0`，声明参数元信息
- `src/nextaiops_algo/algorithms/iqr.py`：声明 `k` 参数元信息，默认 `1.5`
- `src/nextaiops_algo/pipeline/run.py`：使用 params 创建算法实例，并保存 normalized params
- `src/nextaiops_algo/ui/app.py`：单算法页用参数表单替代 JSON，展示默认值和参数含义
- 测试：
  - `tests/unit/test_algorithm_params.py`
  - `tests/unit/test_run.py`
  - `tests/unit/test_three_sigma.py`
  - `tests/unit/test_iqr.py`

**关键设计点**：
- 参数元信息放在 `algorithms/` 可变层，不进入 `core/`。
- REGISTRY 可继续保存默认算法实例；运行实验时根据参数创建新的算法对象，避免跨 run 状态污染。
- 参数表单按类型渲染：number input / slider / selectbox / checkbox。
- 实验标识建议由 `algorithm_name + normalized_params + dataset_version + split_config` 生成。
- 未声明参数元信息的算法优雅降级为 JSON 参数输入，便于 TSB-UAD adapter 后续逐步补齐。

**验收线**：
- [ ] UI 能看到参数默认值、类型与含义
- [ ] `three_sigma k=2` 与 `k=3` 的检测结果可产生差异
- [ ] `iqr k=1.5` 默认行为不回归
- [ ] run record 中保存 normalized params
- [ ] 单算法页展示可读实验标识，例如 `three_sigma[k=3.0]`
- [ ] `make test` 与 `make smoke` 通过

**红线映射**：R2（算法仍消费/产出 Table），R3（参数参与复现记录），R6（不引入 PLAN 未声明依赖）

---

## PR-2（M1.5）：数据预览增强

**目标**：让用户在运行实验前理解数据质量、字段角色、指标走势与真实异常标签分布，避免盲目调参。

**范围**：
- `src/nextaiops_algo/pipeline/profile.py`：新增数据画像函数
- `src/nextaiops_algo/viz/preview.py`：新增数据预览图
- `src/nextaiops_algo/ui/app.py`：增强数据预览区
- 测试：
  - `tests/unit/test_profile.py`
  - `tests/unit/test_viz_preview.py`

**数据画像内容**：
- 行数、列数、字段角色、dtype、缺失率
- METRIC 列数量与名称
- LABEL 存在时展示真实异常点数、异常比例、连续异常段数、最长异常段长度
- 无 LABEL 时明确提示“无法计算真实异常统计”

**预览图要求**：
- 默认展示第一个 METRIC 指标曲线
- 多 METRIC 时支持选择指标
- 有真实 LABEL 时叠加异常点或异常区间
- 无 TIMESTAMP 时使用 index 作为 x 轴

**验收线**：
- [ ] 上传或选择数据后，无需运行实验即可看到指标曲线
- [ ] 可看到真实异常数量、异常比例、异常段数量
- [ ] 有 LABEL 时叠加真实异常；无 LABEL 时优雅降级
- [ ] 多 METRIC 可切换查看
- [ ] `make test` 通过

**红线映射**：R2（预览只消费 Table），R5（测试不吞异常）

---

## PR-3（M1.5）：实验结果解释增强

**目标**：让实验结果不仅显示指标分数，还说明真实异常、检出异常、命中、误报、漏检，并在曲线上直观看出算法表现。

**范围**：
- `src/nextaiops_algo/pipeline/diagnostics.py`：新增检测诊断函数
- `src/nextaiops_algo/viz/timeseries.py` 或 `src/nextaiops_algo/viz/result.py`：增强结果曲线
- `src/nextaiops_algo/ui/app.py`：升级单算法结果展示
- 测试：
  - `tests/unit/test_diagnostics.py`
  - `tests/unit/test_timeseries.py`

**诊断内容**：
- `true_anomalies`
- `predicted_anomalies`
- `tp` / `fp` / `fn` / `tn`
- `true_segments`
- `hit_segments`

**结果图要求**：
- 真实异常段用背景带或独立标记展示
- TP / FP / FN 使用不同视觉标记
- hover 展示 timestamp/index、metric value、真实标签、预测标签、score、threshold、分类结果
- 多 METRIC 默认展示第一个 metric，后续可扩展 metric selector

**指标说明要求**：
- Precision：检出的异常中有多少是真的，越高说明误报越少
- Recall：真实异常中有多少被检出，越高说明漏报越少
- F1：Precision 与 Recall 的综合平衡
- PA-F1：按异常段调整后的 F1，更贴近运维场景

**验收线**：
- [ ] 结果表格显示真实异常数、检出异常数、TP / FP / FN / TN
- [ ] 指标表包含 Precision / Recall / F1 / PA-F1 的含义说明
- [ ] 曲线能区分命中、误报、漏检
- [ ] 不改变算法输出 Table 契约
- [ ] `make test` 与 `make smoke` 通过

**红线映射**：R2（诊断在 pipeline/viz 层，不进入算法），R5（测试不改断言）

---

## PR-4（M1.5）：单算法交互与视觉 polish

**目标**：降低按钮堆叠感，让单算法页更像专业 AIOps 工作台，而不是临时 demo。

**范围**：
- `src/nextaiops_algo/ui/app.py`
- `src/nextaiops_algo/viz/preview.py`
- `src/nextaiops_algo/viz/timeseries.py`

**交互原则**：
- 图表操作主要依赖 Plotly 原生鼠标交互：hover、legend 隐藏/显示、框选缩放、拖拽平移、双击复位
- 减少图表外部按钮式切换
- 参数配置与数据选择靠近实验入口，结果解释与主图靠近展示区

**展示建议**：
- 单算法页布局调整为：数据源与算法配置在侧栏或左栏，主区域上方数据预览，下方实验结果与解释图
- 使用语义色表达 TP / FP / FN，不使用大面积装饰性渐变
- 指标卡片数量控制在 4 到 6 个，详细解释放入表格或 expander

**验收线**：
- [ ] 单算法页主流程无需频繁切换按钮即可完成查看
- [ ] hover 信息足够解释单点判断
- [ ] 结果区域视觉层次清楚，图表为主，表格为辅
- [ ] `make demo` 能完整走通单算法实验

**红线映射**：R6（UI 不写业务逻辑，只调用 pipeline/viz/storage）

---

## PR-5（M1.5）：DatasetBundle 多文件 / zip 输入

**目标**：支持上传多个文件或压缩包作为同一个数据集，并在同一 schema 约束下运行单算法实验。

**范围**：
- `src/nextaiops_algo/pipeline/dataset_bundle.py`：新增 DatasetBundle / DatasetFile 模型与加载逻辑
- `src/nextaiops_algo/pipeline/preprocess.py`：复用现有 `read_to_table`，增加 bundle 分发入口
- `src/nextaiops_algo/ui/app.py`：支持多文件上传与 zip 上传
- 可选：`src/nextaiops_algo/pipeline/run_bundle.py`：逐文件运行单算法并聚合结果
- 测试：
  - `tests/unit/test_dataset_bundle.py`
  - `tests/integration/test_single_bundle_experiment.py`

**关键设计点**：
- M1.5 默认采用“同一数据集内逐文件独立运行，再汇总”的策略，不先拼接为一个 Table。
- 同一 DatasetBundle 内字段角色必须一致；不一致时 fail-fast，并展示具体文件差异。
- zip 仅解包支持的输入文件类型；忽略隐藏文件与目录。
- 多文件结果展示包含 dataset 级汇总与 file 级明细。

**验收线**：
- [ ] 多个 CSV 可作为同一 dataset 上传并通过 schema 一致性校验
- [ ] zip 中多个支持文件可被识别并加载
- [ ] schema 不一致时提示具体冲突
- [ ] 单算法可对每个文件独立运行并展示汇总结果
- [ ] 不改变单文件输入行为
- [ ] `make test` 与 `make smoke` 通过

**红线映射**：R3（每个 run 仍需落库与保留参数），R5（失败不能吞异常），R6（不引入未声明依赖）

---

## M1.5 推荐实施顺序

1. PR-1：先修通参数元信息与参数生效链路，解决功能正确性问题。
2. PR-2：补数据预览，提升实验前判断能力。
3. PR-3：补结果解释与 GT/TP/FP/FN 可视化，提升实验后判断能力。
4. PR-4：做交互与视觉 polish。
5. PR-5：最后落多文件 / zip DatasetBundle，避免过早扩大 pipeline 和 storage 复杂度。

---

# M1.6 任务拆解：批量实验工作台增强

> M1.6 聚焦把“批量实验”从单文件多算法对比，升级为支持 DatasetBundle 的多文件 / zip 批量对比工作台。
> 本阶段延续 M1.5 的保守边界：不修改 `core/` 既有接口，不改 SQLite schema，不引入新依赖；每个单元实验继续通过 `run_experiment()` 落库，批量二维汇总先写入 artifacts summary。

## M1.6 总验收线

打通批量实验增强闭环：
**选择或上传单文件 / 多文件 / zip → 选择多个算法 → 运行算法 × 文件矩阵 → 查看总排行榜 + 文件矩阵热力图 + 单文件多算法钻取 → 保留 summary artifacts**

完成标准：
- [x] 批量实验页支持 DatasetBundle 多文件 / zip 输入，不再要求切回单文件
- [x] 多算法 × 多文件运行时单个 cell 失败不阻断整体批量实验
- [x] 每个成功 cell 仍通过 `run_experiment()` 独立落库，满足复现与追踪要求
- [x] 批量 bundle 结果写出 `batch_bundle_summary.json`
- [x] UI 展示算法级聚合排行榜（mean / median / min / success_rate）
- [x] UI 展示算法 × 文件热力图或矩阵，能看出哪个算法在哪个文件翻车
- [x] UI 支持选择单个文件查看该文件上的多算法叠加对比
- [x] 单文件批量实验原行为不回归

## PR-1（M1.6）：批量 DatasetBundle 引擎

**目标**：新增多算法 × 多文件批量运行引擎，复用现有 `DatasetBundle` 与 `run_experiment()`，保持每个 cell 独立落库。

**范围**：
- `src/nextaiops_algo/pipeline/batch_bundle.py` ← 新增
- `tests/unit/test_batch_bundle.py` ← 新增
- `tests/integration/test_batch_bundle_e2e.py` ← 新增

**关键设计点**：
- 新增轻量结果模型，放在 `pipeline/` 可变层，避免修改 `core/experiment.py`：
  - `BatchBundleCellResult`：单个 `algorithm_name × file_name` 的运行结果、状态与错误信息
  - `BatchBundleResult`：批量 bundle 的二维结果、聚合指标、summary artifacts 路径
- 运行顺序按算法外层、文件内层：
  1. 解析算法列表（支持 `"__all__"`）
  2. 遍历算法与 bundle 文件
  3. 调用 `run_experiment(dataset_file.path, algorithm_name, params, output_dir, split_ratio)`
  4. 成功记录 `RunResult`，失败记录 cell error 并继续
  5. 按算法聚合 mean / median / min / success_rate 等指标
  6. 写出 `batch_bundle_summary.json`
- `params_override` 仍按算法名传入，不按文件单独配置。
- 不改现有 `run_batch()`，单文件批量实验继续使用原逻辑。

**验收线**：
- [x] 两个算法 × 两个文件可跑通并返回 4 个 cell
- [x] 未注册算法只标记对应 cell failed，不阻断其他算法
- [x] 单个文件失败不阻断同一算法的其他文件
- [x] algorithm-level 聚合指标包含 `mean_pa_f1` / `median_pa_f1` / `min_pa_f1` / `success_rate`
- [x] `batch_bundle_summary.json` 包含 batch_bundle_id / dataset_id / algorithms / files / cells / algorithm_metrics
- [x] 不改变 `run_batch()` 单文件行为

**红线映射**：R2（仍经 pipeline 调用算法，算法 I/O 不变），R3（每个成功 cell 独立落库），R5（失败不吞异常，记录上下文），R6（不引入新依赖）

## PR-2（M1.6）：批量 DatasetBundle 可视化

**目标**：为二维批量结果提供适合“算法 × 文件”分析的可视化与表格。

**范围**：
- `src/nextaiops_algo/viz/batch_bundle.py` ← 新增
- `tests/unit/test_viz_batch_bundle.py` ← 新增

**关键设计点**：
- 新增 `render_bundle_algorithm_leaderboard(result)`：一行一个算法，默认按 success_rate 与 mean_pa_f1 排序。
- 新增 `render_bundle_file_matrix(result, metric="pa_f1")`：返回算法 × 文件矩阵 DataFrame。
- 新增 `render_bundle_heatmap(result, metric="pa_f1")`：Plotly 热力图，failed cell 显示为空值或失败标记。
- 单文件钻取时复用现有 `render_overlay()`，必要时构造只包含该文件成功 runs 的轻量 `BatchRun` 视图。

**验收线**：
- [x] 排行榜能展示成功率与聚合指标
- [x] 矩阵能展示每个算法在每个文件上的指标
- [x] 热力图能处理 failed cell，不报错
- [x] 指定不存在 metric 时优雅降级为空值

**红线映射**：R2（viz 只消费结果对象，不触碰算法），R5（测试覆盖失败 cell）

## PR-3（M1.6）：批量实验 UI 接入

**目标**：让 Streamlit 批量实验页支持 DatasetBundle，并提供不同于单算法页的二维对比工作台体验。

**范围**：
- `src/nextaiops_algo/ui/app.py`
- 如有必要，补充 `tests/integration/test_batch_bundle_e2e.py`

**关键设计点**：
- 输入为单文件时沿用现有 `run_batch()` 与三件套。
- 输入为 DatasetBundle 时调用 `run_batch_bundle()`。
- 运行前展示任务数：`算法数 × 文件数`。
- 运行后展示四块：
  1. 算法总排行榜：mean / median / min / success_rate
  2. 算法 × 文件矩阵 / 热力图
  3. 文件钻取：选择文件后展示该文件的多算法 overlay
  4. Cell 明细：展示每个算法 × 文件的 run_id / 状态 / 错误信息
- 不在 UI 中重算算法结果；UI 仅调用 pipeline/viz/storage。

**验收线**：
- [x] DatasetBundle 输入进入批量页后可以直接运行
- [x] UI 显示任务数与结果矩阵
- [x] 选择某个文件能查看该文件成功算法的叠加对比
- [x] failed cell 不影响其他结果展示
- [x] 单文件批量页原排行榜 / overlay / heatmap 仍可用

**红线映射**：R3（展示已落库 run_id），R6（UI 不写业务逻辑）

---

## M1 → M2 候选 proposal（仅参考）

| ID  | 标题 | 备注 |
| --- | --- | --- |
| 012 | 多数据集批量实验（算法 × 数据集完整矩阵） | 扩展 batch 引擎 |
| 013 | 箱线图 + CD 图（多数据集稳定性分析） | 需 012 |
| 014 | Range-F1 / VUS 高级指标 | 评估体系完善 |
| 015 | 并行执行引擎（multiprocessing / Ray） | 规模 >10 时需要 |
| 016 | 深度学习算法桥接（LSTM-AE / CNN / TranAD） | GPU + PyTorch / TensorFlow 依赖管理 |
| 017 | 自定义阈值策略插件化 | 从 adapter 硬编码抽离 |
| 018 | 模型 + 配置打包导出 | M0 候选 005 延续 |
| 019 | MLflow 后端集成 | M0 候选 010 延续 |
| 020 | 用户自定义 schema 覆盖 | M0 候选 006 延续 |
| 021 | ENTITY 角色与多实体训练 | M0 候选 007 延续 |
| 022 | LABEL_WINDOW / NAB 窗口标签 | M0 候选 008 延续 |
| 023 | 按 metric 分别输出与评估 | M0 候选 009 延续 |
| 024 | UI 产品设计与正式工作台重构 | 已纳入 M2-024 |
| 025+ | 自动下载 / 缓存 TSB-UAD Public v2 | 需数据许可与缓存策略确认，延后到 M2+ 重新编号 |

---

# 附录 A：替换本地 PLAN.md 的操作步骤

## 方式 1：直接覆盖

在仓库根目录执行：

```bash
cp /path/to/downloaded/PLAN_merged_M0_M1.md nextaiops-algo-app/docs/PLAN.md
git diff -- nextaiops-algo-app/docs/PLAN.md
```

确认 diff 后提交：

```bash
git add nextaiops-algo-app/docs/PLAN.md
git commit -m "docs: merge M1 batch experiment plan"
```

## 方式 2：人工追加 M1

如果你希望 M0 原文完全不动，只追加 M1：

1. 打开本文件。
2. 从 `# M1 任务拆解：可视化批量实验能力` 开始复制到文件末尾。
3. 追加到本地 `nextaiops-algo-app/docs/PLAN.md` 的末尾。
4. 将本地原文件中的 `## M0 → M1 候选 proposal（仅参考，不在 M0 范围）` 可保留，也可替换为本文件中的“已融合进 M1”版本。

## 覆盖后验证

```bash
cd next-aiops-system/nextaiops-algo-app
grep -n "M1 任务拆解" docs/PLAN.md
grep -n "TSB-UAD" docs/PLAN.md
git diff -- docs/PLAN.md
```

如果当前 M0 仍在进行，建议只提交文档，不启动 M1 代码改动。

---

# 附录 B：TSB-UAD 本地验证命令

```bash
cd next-aiops-system/nextaiops-algo-app

python -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
make smoke

pip install -e ".[dev,tsbuad]"
python - <<'PY'
from TSB_UAD.models.iforest import IForest
from TSB_UAD.models.lof import LOF
from TSB_UAD.models.ocsvm import OCSVM
from TSB_UAD.models.pca import PCA
from TSB_UAD.models.hbos import HBOS

print("TSB-UAD imports OK")
PY

make smoke-tsbuad
```

> 注意：如果本地 Python / TensorFlow 依赖冲突，先不要把问题扩散到默认开发环境。M1 PR-3 应优先保证“未安装 extras 时 graceful degradation”。

---

# 附录 C：M1 PR 启动模板

```markdown
## Scope Anchor

> 原文引用本 PR 的“范围”段落。

## 本 PR 做什么

- ...

## 本 PR 不做什么

- ...

## 验收方式

- [ ] make lint
- [ ] make test
- [ ] make smoke
- [ ] 如涉及 tsbuad：make smoke-tsbuad

## 风险与回滚

- ...
```

---

# M2 任务拆解：持续学习与模型生命周期管理

> M2 聚焦客户最关心的问题：算法如何基于线上持续累积的数据，对数据特征进行持续学习，并形成可评估、可上线、可回滚的模型版本。
>
> 从 M2 开始，任何新增功能必须先按 `changes/_template/` 在 `changes/proposed/<id>/` 下写 proposal，明确目标、范围、spec diff、任务和验收标准。
>
> 默认不得修改 `core/` 既有接口。若必须修改 `core/` 既有接口，必须先补 ADR / 架构评审说明。Proposal 通过 review 前，不得进入代码实现。

## M2 总目标

将 NextAIOpsAlgoApp 从“实验验证平台”推进为“持续学习型算法平台”。

目标闭环：

```text
Daily Data
→ Dataset Partition
→ Training Dataset Version
→ Train Job
→ Model Version
→ Evaluation Report
→ Promotion
→ Active Model
```

面向客户的能力表达：

```text
平台可按天接收线上新增数据，将最近一天数据与历史窗口数据组合成可追溯的训练数据集版本；
算法基于该训练集重新学习指标分布特征，例如均值、方差、分位数、异常阈值或模型参数；
每次训练产出新的候选模型版本，并与当前线上模型进行评估对比；
满足晋级条件后，模型可被标记为 active model，并支持后续回滚和追溯。
```

## M2 总验收线

完成 M2 后，应至少满足：

- [ ] 完成正式 UI 产品设计：信息架构、关键页面、核心流程、视觉规范、交互状态
- [ ] UI 设计文档落地到 `docs/product/ui/*`，不在该阶段修改 UI 代码
- [ ] 完成 UI 技术选型评估，明确继续使用 Streamlit 或迁移到更正式前端的判断依据
- [ ] 支持按天登记线上新增数据分区
- [ ] 支持基于 rolling window 构建训练数据集版本
- [ ] 每个训练数据集版本有稳定 fingerprint
- [ ] 支持基于训练数据集执行 train job
- [ ] `three_sigma` / `iqr` 至少支持生成可保存、可加载、可复用的模型 artifact
- [ ] 支持 model version 记录
- [ ] 支持 candidate / active / archived 模型状态
- [ ] 支持候选模型与当前 active model 的指标对比
- [ ] 支持手动 promote 新模型为 active model
- [ ] 支持使用指定 model version 对新数据执行 predict
- [ ] 所有新增能力均先经过 `changes/proposed/<id>/` proposal review
- [ ] 不破坏 M0 ~ M1.6 的 run / batch / bundle / UI 既有行为

---

## M2 工程治理规则

从 M2 开始，所有新增能力遵循：

```text
需求想法
→ changes/proposed/<id>/proposal
→ 明确目标 / 非目标 / 范围 / spec diff / 任务 / 验收标准
→ review
→ 如涉及 core/ 既有接口变更，补 ADR / 架构评审
→ proposal 通过
→ 进入代码实现
→ 测试 / 文档 / 验收
```

硬性约束：

- [ ] 不允许绕过 proposal 直接改 `src/`
- [ ] 不允许绕过 proposal 直接新增 CLI
- [ ] 不允许绕过 proposal 直接改 SQLite schema
- [ ] 不允许默认修改 `core/` 既有接口
- [ ] 不允许在 proposal 通过前实现代码
- [ ] 每个 implementation PR 必须引用对应 proposal 作为 scope anchor

---

## M2 当前代码基线

基于当前代码核查：

| 能力 | 当前状态 |
| --- | --- |
| 算法接口 | 有 `fit(data)` / `detect(data)`，但无 `predict()` / `save()` / `load()` |
| 统计类算法状态 | `three_sigma` / `iqr` 只在实例内保存 `_stats` |
| TSB-UAD 模型状态 | adapter 内存中保存 `_metric_models` 等，不形成平台模型版本 |
| DatasetBundle | 可表达多文件集合，但不能表达 day partition / rolling window |
| SQLite schema | 仅有 `runs` / `metrics` / `batches` / `batch_runs` |
| 数据指纹 | 未实现 |
| 训练任务 | 未实现 |
| 模型版本 | 未实现 |
| active model | 未实现 |
| train / export / predict / promote CLI | 未实现 |
| 新旧模型对比 | 未实现 |

因此 M2 的第一优先级不是继续增加算法，而是并行推进两条主线，并在持续学习工作台汇合：

```text
设计轨：UI 产品设计 → 技术选型评估 → M2-029 工作台实现
领域轨：数据版本
→ 训练任务
→ 模型版本
→ 模型晋级
→ M2-029 工作台实现
```

---

## M2 Proposal 列表

| 顺序 | Proposal ID | 标题 | 目标 | 是否允许修改 core/ 既有接口 |
| ---: | --- | --- | --- | --- |
| 024 | `ui-product-design-prototype` | UI 产品设计 + 可评审 HTML 原型 | 信息架构、用户旅程、页面蓝图、静态 HTML 原型、技术选型评估 | 否 |
| 025 | `continuous-learning-dataset-versioning` | 持续学习数据集版本化 | 每日数据分区 + rolling window 训练数据集版本 | 否 |
| 026 | `trainable-model-artifacts` | 可训练模型 artifact | three_sigma / iqr 生成可保存、可加载模型 | 默认否；如必须修改需 ADR |
| 027 | `model-version-registry` | 模型版本注册表 | train job / model version / model artifact 元数据管理 | 否 |
| 028 | `model-promotion-lifecycle` | 模型晋级生命周期 | candidate / active / archived / promote / rollback | 否 |
| 029 | `continuous-learning-workbench-implementation` | 持续学习工作台实现 | 基于 M2-024 设计落地数据分区、训练集、模型版本、新旧对比 UI | 否 |
| 030 | `scheduled-training-integration` | 周期训练集成 | 为外部调度器或后续 scheduler 暴露稳定入口 | 否，延后 |

M2 推荐只承诺 024 ~ 029。  
030 可作为 M2+ 或 M3 候选，避免过早引入调度器、队列、服务化复杂度。

---

# M2-024：ui-product-design-prototype

## 目标

先完成正式 UI 产品设计，并产出可本地打开、可评审、带用户旅程解释的静态 HTML 原型，避免后续工作台实现继续被现有 Streamlit 页面结构反向约束产品体验。

M2-024 是 UI 实现前置，不阻塞 M2-025 ~ M2-028 的数据、训练、模型版本与晋级主线。  
M2-024 只阻塞 M2-029 的 UI implementation。

本阶段重点回答：

```text
这个算法平台应该如何被客户理解和使用？
哪些页面承载核心工作流？
数据、实验、批量评估、模型版本、上线模型之间如何导航？
当前 Streamlit 是否仍能承载目标体验？
```

设计必须围绕客户演示主线，而不是只追求页面好看：

```text
模型从哪些数据学习？
学到了什么数据特征？
为什么这个候选模型可以上线？
上线后如何追溯与回滚？
```

## 范围

本 change 只允许先写 proposal，不直接实现代码。

Proposal 应定义：

- 目标用户与核心场景
- 客户演示主线与用户旅程
- 全局信息架构
- 主导航结构
- 关键页面清单
- 单算法实验页重构方向
- 批量实验页重构方向
- 持续学习 / 模型管理页面蓝图
- 统一视觉规范：颜色、字体层级、表格、指标卡、状态标签、矩阵、详情区、空状态、错误状态
- 关键交互状态：加载中、运行中、失败、部分失败、不可操作、已完成、已晋级
- UI 技术选型评估标准：继续 Streamlit、重构 Streamlit、或迁移到 React / Next.js 等正式前端
- 可本地打开的静态 HTML 原型交付方式

Proposal 通过后的 implementation PR 只允许新增 / 修改：

- `docs/product/ui/`

implementation PR 应产出设计文档与静态 HTML 原型，不修改 `src/`、不重构 UI 代码、不新增前端工程。

必须规划以下设计交付物：

1. `docs/product/ui/user-journeys.md`
2. `docs/product/ui/page-spec.md`
3. `docs/product/ui/interaction-states.md`
4. `docs/product/ui/visual-guidelines.md`
5. `docs/product/ui/tech-decision.md`
6. `docs/product/ui/prototype/index.html`

其中 `prototype/index.html` 必须是可本地打开的静态 HTML 原型，用 mock 数据展示核心页面和用户旅程说明，不连接真实后端，不调用 pipeline，不引入新运行时依赖。

## 非目标

本 change 不做：

- 直接重构 `src/nextaiops_algo/ui/app.py`
- 修改任何 `src/` 代码
- 直接新增前端工程
- 直接迁移到 React / Next.js
- 实现持续学习业务逻辑
- 修改 SQLite schema
- 修改 `core/` 既有接口
- 修改 `tests/`
- 修改 `storage/schema.sql`
- 修改 `pyproject.toml`
- 引入新运行时依赖

## 页面蓝图草案

建议至少覆盖：

```text
Overview
Data
Experiments
Batch Compare
Continuous Learning
Models
History
Settings
```

关键页面职责：

- `Overview`：展示当前 active model、最近训练、最近实验、系统状态
- `Data`：展示数据分区、schema、fingerprint、数据质量
- `Experiments`：承载现有单算法实验能力
- `Batch Compare`：承载现有批量评估、排行榜、矩阵、热力图
- `Continuous Learning`：展示 rolling window、train job、训练数据集版本
- `Models`：展示 model versions、candidate vs active、promote / rollback
- `History`：统一 run / batch / train job / promotion event 查询

## 技术选型评估草案

Proposal 应明确评估：

- 继续 Streamlit 的边界与可接受妥协
- 何时需要迁移到正式前端
- 如果继续 Streamlit，如何组织页面、状态与组件，降低单文件 UI 膨胀
- 如果迁移前端，M2 是否只做设计，M3 再做工程化迁移

默认建议：

```text
M2-024 只做设计和技术判断；
M2-029 再根据设计结论决定是 Streamlit 重构，还是启动独立前端 proposal。
```

## 验收标准

Proposal 通过后，应至少产出：

- [ ] 用户角色与核心用例列表
- [ ] 全局导航与页面信息架构
- [ ] 关键页面低保真结构
- [ ] 客户演示主线：模型从哪些数据学习、学到了什么、为什么能上线、如何追溯和回滚
- [ ] 核心流程图：数据 → 实验 → 批量评估 → 持续学习 → 模型上线
- [ ] 视觉规范草案
- [ ] 交互状态清单
- [ ] Streamlit 是否继续使用的评估结论与理由
- [ ] 已产出可本地打开的静态 HTML 原型：`docs/product/ui/prototype/index.html`
- [ ] HTML 原型包含 Overview / Data / Experiments / Batch Compare / Continuous Learning / Models / History / Settings 页面
- [ ] HTML 原型支持基础页面切换，不连接真实后端
- [ ] 每个页面包含“页面目标 / 用户动作 / 核心信息 / 下一步动作”说明
- [ ] HTML 原型展示关键状态：empty / loading / running / failed / partial_failed / candidate / active / archived
- [ ] 已产出用户旅程文档：`docs/product/ui/user-journeys.md`
- [ ] 已产出页面功能点说明：`docs/product/ui/page-spec.md`
- [ ] 已产出交互状态说明：`docs/product/ui/interaction-states.md`
- [ ] 已产出视觉规范说明：`docs/product/ui/visual-guidelines.md`
- [ ] 已产出 UI 技术选型评估：`docs/product/ui/tech-decision.md`
- [ ] M2-024 implementation 不修改 `src/`、`tests/`、`storage/schema.sql`、`pyproject.toml`
- [ ] 后续 UI implementation proposal 的范围建议

---

# M2-025：continuous-learning-dataset-versioning

## 目标

为持续学习场景建立数据层基础，使平台能够表达：

```text
每日新增数据
→ 历史窗口选择
→ 训练数据集版本
→ 稳定 fingerprint
→ 后续 train job 可引用
```

## 范围

本 change 只允许先写 proposal，不直接实现代码。

Proposal 应定义：

- `DatasetPartition`
- `TrainingDataset`
- `TrainingPolicy`
- daily partition ingest 行为
- rolling window training dataset 构建行为
- training dataset fingerprint 规则
- list training datasets 行为

## 非目标

本 change 不做：

- 模型训练
- 模型导出
- 模型版本管理
- 模型晋级
- REST API
- 调度器
- `fit / predict / save / load` 生命周期改造
- `core/` 既有接口修改

## CLI 草案

```bash
nextaiops_algo ingest \
  --data data/2026-05-18.csv \
  --date 2026-05-18 \
  --dataset prod_cpu
```

```bash
nextaiops_algo build-dataset \
  --dataset prod_cpu \
  --mode rolling_window \
  --end-date 2026-05-18 \
  --history-window-days 30
```

```bash
nextaiops_algo list-datasets
```

## 存储草案

建议新增表：

```text
dataset_partitions
training_datasets
```

但实际 schema 必须在 proposal 中确认，review 通过后才能实现。

## 验收标准

Proposal 通过后，implementation 应满足：

- [ ] 能登记指定日期的数据分区
- [ ] 不通过文件名猜日期，必须显式传入 `partition_date`
- [ ] 能按 `end_date + history_window_days` 选择训练窗口
- [ ] schema 不一致时 fail-fast
- [ ] 相同 partitions + policy 生成相同 fingerprint
- [ ] policy 或 partitions 改变后 fingerprint 变化
- [ ] 不影响现有 `run` / `batch` / `DatasetBundle` 行为
- [ ] 不修改 `core/` 既有接口
- [ ] `make test` / `make smoke` 通过

---

# M2-026：trainable-model-artifacts

## 目标

让平台至少支持 `three_sigma` / `iqr` 生成可保存、可加载、可复用的模型 artifact，使“算法持续学习数据特征”有第一版落点。

当前算法虽然有 `fit()`，但训练结果只保存在实例内存中：

```text
three_sigma: _stats
iqr: _stats
```

M2-026 应将这些训练结果转化为平台可管理的模型 artifact。

## 范围

Proposal 应定义：

- 统计类模型 artifact 格式
- model artifact 目录结构
- train 命令草案
- predict 命令草案
- model artifact 与 TrainingDataset 的关系
- 如何在不修改 `core/` 既有接口的前提下实现模型化

## 非目标

本 change 不做：

- TSB-UAD 模型持久化
- 深度学习模型导出
- 自动模型晋级
- active model 管理
- REST API
- 调度器

## 模型 artifact 草案

```text
.nextaiops_algo/models/<model_id>/
  model.json
  params.json
  training_dataset.json
  schema.json
  metrics.json
  README.md
```

`three_sigma` 的 `model.json` 至少包含：

```json
{
  "algorithm_name": "three_sigma",
  "params": {"k": 3.0},
  "metrics": {
    "value": {
      "mean": 10.3,
      "std": 1.2,
      "lower": 6.7,
      "upper": 13.9,
      "count": 1000
    }
  }
}
```

`iqr` 的 `model.json` 至少包含：

```json
{
  "algorithm_name": "iqr",
  "params": {"k": 1.5},
  "metrics": {
    "value": {
      "q1": 8.0,
      "q3": 12.0,
      "iqr": 4.0,
      "lower": 2.0,
      "upper": 18.0,
      "count": 1000
    }
  }
}
```

## CLI 草案

```bash
nextaiops_algo train \
  --training-dataset-id <training_dataset_id> \
  --algo three_sigma \
  --params '{"k": 3}'
```

```bash
nextaiops_algo predict \
  --model-id <model_id> \
  --data data/latest.csv
```

## 验收标准

Proposal 通过后，implementation 应满足：

- [ ] `three_sigma` 训练后生成 `model.json`
- [ ] `iqr` 训练后生成 `model.json`
- [ ] `predict` 必须加载 model artifact，不允许重新 `fit`
- [ ] model artifact 记录 params、schema、training_dataset、训练统计量
- [ ] 同一模型对同一数据 predict 结果稳定
- [ ] 不破坏现有 `run_experiment()` 行为
- [ ] 如需修改 `AnomalyDetector`，必须先补 ADR / 架构评审

---

# M2-027：model-version-registry

## 目标

引入模型版本注册能力，使每次 train job 产生的模型 artifact 成为可查询、可追溯、可评估的 model version。

## 范围

Proposal 应定义：

- `TrainJob`
- `ModelVersion`
- `ModelStatus`
- model artifact path 记录方式
- train job 与 training dataset 的关联
- model version 与 run / metrics / artifact 的关系

## 非目标

本 change 不做：

- 自动晋级
- active model
- rollback
- REST API
- 调度器
- UI 管理页

## 状态草案

```text
TrainJobStatus:
- PENDING
- RUNNING
- SUCCEEDED
- FAILED
- CANCELLED

ModelStatus:
- CANDIDATE
- FAILED
- ARCHIVED
```

`ACTIVE` 状态放到 M2-028 中引入。

## 存储草案

建议新增表：

```text
train_jobs
model_versions
```

## 验收标准

Proposal 通过后，implementation 应满足：

- [ ] train job 可落库
- [ ] train job 失败时记录 error_message
- [ ] 成功 train job 生成 model version
- [ ] model version 可查询
- [ ] model version 能追溯到 training dataset
- [ ] model version 能追溯到 artifact path
- [ ] 不影响现有 runs / batches 查询

---

# M2-028：model-promotion-lifecycle

## 目标

支持模型从候选状态晋级为线上 active model，并保留晋级记录和回滚基础。

## 范围

Proposal 应定义：

- active model 的唯一性规则
- model scope
- promote 行为
- archive 旧模型行为
- promotion event 记录
- active model 查询
- candidate vs active model 对比

## 非目标

本 change 不做：

- 自动晋级策略
- 多人审批流
- 权限系统
- REST API
- 在线 serving
- 调度器

## 状态草案

```text
ModelStatus:
- CANDIDATE
- ACTIVE
- ARCHIVED
- FAILED
```

## CLI 草案

```bash
nextaiops_algo evaluate-model \
  --model-id <candidate_model_id> \
  --data data/validation.csv
```

```bash
nextaiops_algo promote \
  --model-id <candidate_model_id> \
  --scope prod_cpu
```

```bash
nextaiops_algo active-model \
  --scope prod_cpu
```

## 存储草案

建议新增表：

```text
active_models
promotion_events
```

## 验收标准

Proposal 通过后，implementation 应满足：

- [ ] candidate model 可被 promote 为 active
- [ ] 同一 scope 下最多只有一个 active model
- [ ] 新模型 active 后，旧 active model 变为 archived
- [ ] promote 事件可追溯 previous_model_id
- [ ] 可查询当前 active model
- [ ] 可对 candidate model 和 active model 做指标对比
- [ ] 不影响历史 run / batch 行为

---

# M2-029：continuous-learning-workbench-implementation

## 目标

基于 M2-024 的正式 UI 设计结论，实现持续学习与模型管理工作台，使客户能直观看到：

```text
每日数据
→ 训练数据集
→ 训练任务
→ 模型版本
→ 当前 active model
→ 新旧模型对比
```

## 范围

Proposal 应引用 M2-024 的设计产物，并定义实现范围。

如果 M2-024 结论是继续使用 Streamlit，则本 change 可以重构现有 Streamlit UI。  
如果 M2-024 结论是迁移到正式前端，则本 change 应降级为前端工程 proposal，不直接在 Streamlit 中堆功能。

建议页面：

```text
持续学习 / 模型管理
```

页面模块：

1. 数据分区列表
2. 训练数据集版本列表
3. Train job 列表
4. Model version 列表
5. 当前 active model
6. Candidate vs active 指标对比
7. Promote 操作入口

## 非目标

本 change 不做：

- 重新定义整体 UI 信息架构（由 M2-024 完成）
- 权限系统
- 多人审批
- 自动调度
- 在线预测服务
- REST API

## 验收标准

Proposal 通过后，implementation 应满足：

- [ ] 实现方式符合 M2-024 的设计和技术选型结论
- [ ] UI 能展示 dataset partitions
- [ ] UI 能展示 training datasets
- [ ] UI 能展示 train jobs
- [ ] UI 能展示 model versions
- [ ] UI 能展示 active model
- [ ] UI 能展示 candidate vs active 指标对比
- [ ] UI 不直接写业务逻辑，只调用 pipeline / storage / viz
- [ ] 单算法实验页、批量实验页不回归

---

## M2 依赖关系图

```text
设计轨：
M2-024 ui-product-design-prototype

领域轨：
M2-025 continuous-learning-dataset-versioning
   ↓
M2-026 trainable-model-artifacts
   ↓
M2-027 model-version-registry
   ↓
M2-028 model-promotion-lifecycle

汇合：
M2-024 + M2-025~028
   ↓
M2-029 continuous-learning-workbench-implementation
```

M2-024 是 UI 实现前置，但不阻塞 M2-025 ~ M2-028 的后端主线。  
没有正式 UI 设计结论，就不应启动 M2-029 的 UI 实现或 Streamlit 大重构。  
M2-025 是持续学习数据链路强前置。  
没有 TrainingDataset，就不应启动 train job / model version。  
没有 ModelVersion，就不应启动 promotion lifecycle。  
没有稳定 CLI / storage 闭环，就不应启动 M2-029 的持续学习工作台实现。

---

## M2 实施顺序建议

### 第一步：只写 proposal

```text
changes/proposed/ui-product-design-prototype/
changes/proposed/continuous-learning-dataset-versioning/
changes/proposed/trainable-model-artifacts/
changes/proposed/model-version-registry/
changes/proposed/model-promotion-lifecycle/
changes/proposed/continuous-learning-workbench-implementation/
```

推荐先写并 review `ui-product-design-prototype` 与 `continuous-learning-dataset-versioning`。  
两者可以并行推进：前者产出 `docs/product/ui/*` 设计文档与静态 HTML 原型，后者启动持续学习数据链路。  
不要一次性实现所有 proposal，也不要在 M2-024 设计未完成前启动 M2-029。

### 第二步：按 proposal 顺序实现

每个实现 PR 必须引用对应 proposal：

```markdown
## Scope Anchor

本 PR 实现：
changes/proposed/ui-product-design-prototype/

## 本 PR 做什么

- 新增 / 更新 `docs/product/ui/*`
- 产出 UI 信息架构、客户演示主线、页面蓝图、视觉规范、技术选型评估
- 产出可本地打开的静态 HTML 原型：`docs/product/ui/prototype/index.html`

## 本 PR 不做什么

- 不修改 `src/`
- 不修改 `tests/`
- 不修改 `storage/schema.sql`
- 不修改 `pyproject.toml`
- 不重构 Streamlit
- 不新增前端工程

## 验收方式

- [ ] make lint
- [ ] make test
- [ ] make smoke
```

### 第三步：实现后更新 PLAN 状态

proposal 通过后，可以在 PLAN 中将对应状态从：

```text
Proposed
```

改为：

```text
Accepted
```

实现完成后改为：

```text
Completed
```

---

## M2 风险与评审问题

以下问题必须在 proposal review 中确认：

1. `DatasetPartition` / `TrainingDataset` 应放入 `core/`，还是放入新的 domain / pipeline 层？
2. 是否需要 SQLite migration 机制？
3. fingerprint 基于原始文件 bytes，还是标准化后的 Table？
4. 多指标文件的训练粒度如何表达？
5. 最近一天数据中包含异常时，训练集构建是否过滤 `label=1`？
6. 无 label 数据如何避免把异常学习成正常？
7. model scope 第一版如何定义？
8. `predict` 是使用指定 model-id，还是默认使用 active model？
9. `three_sigma` / `iqr` 是否通过新增 adapter 实现模型持久化，避免修改 `AnomalyDetector`？
10. TSB-UAD 模型持久化是否进入 M2，还是延后到 M2+？
11. 是否需要人工 promote，还是支持自动 promote？
12. M2 是否继续使用 Streamlit，还是只保留 Streamlit 到 M1.6 并为 M3 前端迁移做准备？
13. 如果继续 Streamlit，是否拆分 `ui/app.py`，避免单文件继续膨胀？
14. UI 是否允许触发 promote，还是只展示状态？

---

## M2 不做事项

M2 暂不做：

- [ ] 深度学习算法桥接
- [ ] GPU 训练
- [ ] 自动调参 / AutoML
- [ ] MLflow 后端替换
- [ ] REST API 服务化
- [ ] Celery / Redis / Ray / Airflow 等调度系统
- [ ] 权限系统
- [ ] 在线实时 serving
- [ ] 真正 `partial_fit` 在线学习
- [ ] OpenRCA metric converter

这些能力可以进入 M2+ / M3 候选。

---

## M2+ 候选 proposal

| ID | 标题 | 备注 |
| --- | --- | --- |
| 031 | Frontend engineering migration | 如 M2-024 判定 Streamlit 不足以承载正式 UI，则进入 M2+ / M3 |
| 032 | TSB-UAD 模型持久化 | 在统计类模型 artifact 稳定后再做 |
| 033 | MLflow optional backend | 基于 model registry / train job 抽象接入 |
| 034 | REST API for model lifecycle | 暴露 train / predict / model version 查询 |
| 035 | Scheduled training integration | 外部调度器或内置 scheduler |
| 036 | AutoML / parameter search | 依赖稳定训练与评估闭环 |
| 037 | OpenRCA metric subset converter | 将 OpenRCA metric 转为弱标签异常检测 benchmark |
| 038 | Entity-aware training | 支持 service / instance / metric 级别模型 scope |
| 039 | Advanced evaluation metrics | Range-F1 / VUS / detection delay / false alarms per hour |
