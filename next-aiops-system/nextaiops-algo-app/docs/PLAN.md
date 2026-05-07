# docs/PLAN.md — M0 任务拆解

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
- `.github/workflows/ci.yml`（先空跑，仅 lint + 测试占位）
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

## 依赖关系图

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

## M0 → M1 候选 proposal（仅参考，不在 M0 范围）

| ID  | 标题 | 依赖 |
| --- | --- | --- |
| 001 | 接入 IsolationForest | M0 完整 |
| 002 | 接入 LSTM-AutoEncoder | 001 |
| 003 | 数据集版本化与多策略切分（含预切分模式） | M0 完整 |
| 004 | 多实验横向对比视图 | M0 完整 |
| 005 | 模型 + 配置打包导出 | M0 完整 |
| 006 | 用户自定义 schema 覆盖（CSV 推断兜底） | M0 完整 |
| 007 | 支持 ENTITY 角色（KPI 多实体场景） | M0 完整 |
| 008 | 支持 LABEL_WINDOW（NAB 窗口标签） | M0 完整 |
| 009 | 按指标分别输出与评估 | M0 完整 |
| 010 | 迁移 MLflow（轻量自研→工业级） | 003 |
| 011 | 评估命名空间包结构（共享 nextaiops 顶级） | 多子系统出现时 |
