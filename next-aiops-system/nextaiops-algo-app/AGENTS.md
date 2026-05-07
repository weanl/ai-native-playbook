# AGENTS.md — NextAIOpsAlgoApp AI 协作规约

> 本文件是 AI 协作的“宪法”，定义所有红线、流程、约定。
> 入口指针见 @CLAUDE.md（精简版，会话自动加载）。

---

## 1. 项目状态

- **代号**：NextAIOpsAlgoApp（NextAIOpsSystem 的算法平台子系统）
- **当前阶段**：M0（Walking Skeleton）
- **项目定位**：@README.md
- **系统总览**：@docs/NextAIOpsSystem.md
- **范围**：@docs/architecture/M0-skeleton.md
- **任务拆解**：@docs/PLAN.md
- **目标**：3 天内打通“上传指标数据 → 字段推断为 Table → 选算法 → 训练 → 评估 → 出图 → 落库”端到端最小闭环
- **验收线**：`make smoke` 全绿 + `make demo` 一次完整 e2e demo 通过

## 2. 核心红线

每条违反即触发“停下报告”机制（参见 §6）。

### R1. 稳定 / 可变分离
- `src/nextaiops_algo/core/` 是稳定层，存放契约（抽象类 / 协议 / 数据模型），**不含执行逻辑**
- 修改 `core/` 既有接口必须先有 ADR（`docs/adr/NNNN-*.md`），否则拒绝
- `core/` 新增文件不强制 ADR，但需在 PR 描述说明动机

### R2. 算法接入契约
- 所有算法必须实现 `core/algorithm.py::Algorithm` 基础协议
  及对应任务子协议（M0 唯一子协议：`algorithms/base.py::AnomalyDetector`）
- 必须注册到 `algorithms/registry.py::REGISTRY`
- 算法 I/O 统一为 `core/table.py::Table`，禁止直接传 ndarray / DataFrame
- 算法必须声明 `required_input_roles`，平台据此前置校验
- 算法必须支持单 METRIC 列与多 METRIC 列输入（按列独立处理）
- 算法不得直接读写存储 / 数据库
- 算法不得依赖 pipeline/ 或除 core/ 之外的内部模块
- 输出 Table 必须满足任务子协议的输出契约（必选列 + 对齐约束）

### R3. 复现性
- 每次实验运行必须落库：`run_id / dataset_version / algorithm_name / params / metrics / artifacts_path / created_at`
- 相同输入（数据集 + 算法 + 参数 + 随机种子）必须产生一致结果
- 随机性来源必须显式设置 seed，禁止依赖系统时间或环境变量

### R4. 冒烟覆盖
- 冒烟实验自动参数化 REGISTRY 内所有注册算法（`tests/smoke/test_e2e_smoke.py`）
- 新算法 PR 必须使 `make smoke ALG=<name>` 通过
- 冒烟断言项：“能跑通 + 产物齐全 + 落库成功 + 非退化（F1 > 0）”
- 冒烟**不卡效果阈值**（如 F1 ≥ 0.8），效果基准属 M1 benchmark 范畴

### R5. 测试纪律
- 测试失败必须改实现；**禁止**改断言、**禁止** try/except 吞异常、**禁止** `pytest.skip`
- 引入 mock 必须在 PR 描述说明原因
- 单测覆盖率 M0 不强制，M1 起 ≥ 70%

### R6. 范围纪律
- 每个 PR 仅修改 @docs/PLAN.md 当前 PR 段落列出的文件路径
- 引入新依赖必须先在 PLAN 中声明并经 review；运行时禁止 `pip install`
- 禁止“顺手优化”无关代码；发现问题先记录到 `docs/TODO.md`

### R7. M0 范围外（不做）
- 在线推理服务、多租户、权限/认证
- 流式数据接入（kafka/pulsar）
- AutoML、自动特征工程
- MLflow 接入（M0 用轻量自研 SQLite 追踪，M1 才考虑迁移）
- 前端工程化（Streamlit 即可）
- 多实体（KPI ID 等 ENTITY 语义）、窗口标签（NAB 风格）、预切分模式

## 3. 编码与质量门

### 语言与工具
- Python 3.11+
- 包管理：`uv`
- 静态检查：`ruff`（lint + format）+ `mypy --strict`
- 测试：`pytest`

### 类型与文档
- 公开 API 类型注解必须完整
- 公开类/函数必须有 docstring（Google 风格），私有可省
- `core/` 内所有抽象必须有 docstring 说明契约语义

### 命名
- 模块/包：snake_case
- 类：PascalCase
- 函数/变量：snake_case
- 常量：UPPER_SNAKE_CASE
- 测试文件：`test_<被测模块>.py`

### 错误处理
- 业务异常用自定义异常类（`core/exceptions.py`）
- 禁止 bare `except:`
- 异常必须携带可定位上下文（run_id / dataset_id / algorithm_name 等）

## 4. Commit / PR 约定

### Commit 格式（Conventional Commits）

格式：`<type>(<scope>): <subject>`，可选 body。
- type：feat / fix / refactor / test / docs / chore
- scope：core / algorithms / pipeline / viz / storage / cli / ui / smoke / ci
- 每个 commit 独立可编译可测

### 分支命名
`feat/pr-<N>-<slug>`，例如 `feat/pr-1-scaffold`

### PR 描述模板
包含以下部分：动机 / 范围 / 影响面（修改/新增文件清单）/ 验证方式 / 已知遗留 / 自检报告（粘贴 /self-check 输出）。

## 5. AI 工作范式

### 标准循环
1. 阅读 @CLAUDE.md 与 @AGENTS.md，复述红线
2. 阅读 @docs/PLAN.md 对应 PR 段落
3. 列 todo 清单（文件级别 + 红线映射 + 验证方式），**不写代码**
4. 等人 review todo
5. 逐项实现：每项 → 跑测试 → commit → 等“继续”
6. 全部完成 → `/self-check`
7. 等人 review 自检报告 → 由人手 push

### 卡壳规则
- 同一问题尝试 2 次未解 → 停下报告
- 30 分钟未推进 → 停下报告
- 不确定语义 → 直接问，不猜

### 禁止行为
- 改测试断言以让测试通过
- try/except 吞异常或 pytest.skip 以让测试通过
- 顺手优化无关代码
- 引入 PLAN 未声明的依赖
- 修改 @CLAUDE.md @AGENTS.md @docs/PLAN.md @docs/NextAIOpsSystem.md @docs/architecture/**（settings.json 已禁）
- `git push` `git reset --hard` `pip install`（settings.json 已禁）

> 注：@README.md 可在 PLAN 显式声明的 PR 中修订（如 PR-6 完善“快速开始”），但默认情况下不要改动。

## 6. 触发停下报告的情形

满足任一条 → 立即停止并向人报告：
- 触碰红线（R1~R7）
- 卡壳超时
- 自检发现 ❌
- 测试反复失败（≥ 2 次）
- 单次输出超过 200 行（多半在猜）

报告格式：

```text
[STOP] 触发原因: <红线编号 / 卡壳 / 其他>
当前状态: <已完成 / 已 commit / 工作区有未提交改动>
建议: <继续 / 撤销 / 求助>
```

## 7. 常用命令

| 命令 | 用途 |
|---|---|
| `make dev` | 启动开发环境（docker compose） |
| `make test` | 运行所有测试（unit + integration + smoke） |
| `make lint` | ruff + mypy |
| `make fmt` | ruff format |
| `make smoke ALG=<name>` | 单算法冒烟 |
| `make demo` | 启动 Streamlit demo |

## 8. Slash Commands

| 命令 | 用途 |
|---|---|
| `/new-pr <N>` | 启动 PR-N 规划，输出 todo |
| `/impl <i>` | 实现 todo 第 i 项 |
| `/self-check` | PR 收尾自检 |
| `/correct <偏离点>` | 纠偏模式 |

## 9. 核心抽象速查（开发必读）

### 9.1 Table（统一数据载体）

`core/table.py::Table` = `pandas.DataFrame` + `TableSchema`，是算法 I/O、可视化、评估的统一载体。

```python
class FieldRole(StrEnum):
    TIMESTAMP = "timestamp"
    METRIC    = "metric"
    LABEL     = "label"
    # M0 仅此 3 种角色，新增需走 ADR

class TableSchema(BaseModel):
    roles: dict[str, FieldRole]              # 列名 → 角色
    def columns_of(self, role: FieldRole) -> list[str]: ...

class Table(BaseModel):
    df: pd.DataFrame
    schema: TableSchema
    def timestamps(self) -> pd.Series | None: ...   # 至多 1 列
    def metrics(self) -> pd.DataFrame: ...          # ≥ 1 列
    def labels(self) -> pd.Series | None: ...       # 至多 1 列
```

### 9.2 Algorithm（三层协议）

```python
# core/algorithm.py — 跨任务最小公约数
class TaskType(StrEnum):
    ANOMALY_DETECTION = "anomaly_detection"   # M0 唯一任务

@runtime_checkable
class Algorithm(Protocol):
    name: ClassVar[str]
    task_type: ClassVar[TaskType]
    required_input_roles: ClassVar[set[FieldRole]]

# algorithms/base.py — 任务子协议
class AnomalyDetector(Algorithm, Protocol):
    task_type            = TaskType.ANOMALY_DETECTION
    required_input_roles = {FieldRole.METRIC}
    def fit(self, data: Table) -> None: ...
    def detect(self, data: Table) -> Table: ...
```

### 9.3 AnomalyDetector 输出 Table 契约

**必选列**：

- `predicted_label`（角色 LABEL，int ∈ {0, 1}）
  多 METRIC 列时为 OR 合并（任一指标超阈值即为 1）；单 METRIC 退化为该列的标签

**推荐列**（缺失时可视化优雅降级，不报错）：

- `timestamp`（角色 TIMESTAMP，输入有则原样逐行带出）
- 每个输入 METRIC 列原值（角色 METRIC，原列名保留）
- `<metric_name>.anomaly_score`（角色 METRIC，对应列的连续分值）
- `<metric_name>.threshold_upper` / `<metric_name>.threshold_lower`（角色 METRIC，对应列的阈值线）

**对齐约束**（强制）：

- 输出 Table 行数必须 == 输入 Table 行数
- 若输入含 TIMESTAMP，输出必须含同名 TIMESTAMP 列，且逐行值与顺序与输入完全一致

> 注 1：阈值线与 score 不新增独立角色，统一用 METRIC + 列名约定。
> 注 2：列名中的 `.` 作为多指标后缀分隔符（如 `value.anomaly_score`）。

### 9.4 CSV → Table 默认推断规则（M0）

| 列名匹配（不区分大小写） | dtype 兜底 | 角色 |
| --- | --- | --- |
| `timestamp` `time` `ts` `datetime` | datetime / int / float | TIMESTAMP |
| `label` `anomaly` `is_anomaly` `y` | — | LABEL |
| 其他数值列 | numeric | METRIC |
| 其他非数值列 | — | **跳过 + WARNING 日志** |

- 至少需有 1 个 METRIC 列，否则抛 `SchemaValidationError`
- 允许 0 或 1 个 TIMESTAMP 列；超过 1 个匹配抛 `SchemaValidationError`
- 允许 0 或 1 个 LABEL 列；超过 1 个抛 `SchemaValidationError`
- 数值型 timestamp 视为整数索引或 Unix 秒/毫秒，可视化按数值轴绘制
- M1 起：CLI/UI 支持显式 schema 覆盖（如 `--timestamp-col=event_time`）

### 9.5 Pipeline 入口校验（fail-fast）

`pipeline/run.py` 在调用算法前后必须校验：

```python
def _validate_input(table: Table, algo: Algorithm) -> None:
    present = set(table.schema.roles.values())
    missing = algo.required_input_roles - present
    if missing:
        raise SchemaValidationError(
            f"算法 {algo.name} 需要角色 {missing}，输入仅提供 {present}"
        )

def _validate_output(input_table: Table, result: Table, algo: Algorithm) -> None:
    if algo.task_type is TaskType.ANOMALY_DETECTION:
        if "predicted_label" not in result.df.columns:
            raise SchemaValidationError("AnomalyDetector 输出缺 predicted_label 列")
        if result.schema.roles.get("predicted_label") != FieldRole.LABEL:
            raise SchemaValidationError("predicted_label 角色必须为 LABEL")
        if len(result.df) != len(input_table.df):
            raise SchemaValidationError(
                f"输出行数 {len(result.df)} != 输入行数 {len(input_table.df)}"
            )
        in_ts = input_table.timestamps()
        if in_ts is not None:
            out_ts = result.timestamps()
            if out_ts is None or not in_ts.reset_index(drop=True) \
                    .equals(out_ts.reset_index(drop=True)):
                raise SchemaValidationError("输出 timestamp 与输入不对齐")
```

### 9.6 评估职责归属

**评估在 pipeline 层，不在算法层**。算法仅产出 detect 结果 Table；pipeline 拿“输入的真实 label”与“输出的 predicted_label”对比：

```python
# pipeline/evaluate.py
def evaluate(input_table: Table, output_table: Table) -> dict[str, float]:
    y_true = input_table.labels()
    y_pred = output_table.df["predicted_label"]
    return {"precision": ..., "recall": ..., "f1": ...}
```

M0 仅计算全局单组 F1（多指标场景下基于 OR 合并的 predicted_label）。
按指标分别评估的需求（`F1.<metric>`）记入 M1。

## 10. M0 → M1 演进准则

- **M0 合格的最终标准**：M1 的若干 proposal 可并行启动，互不动 `core/`
- **M1 起**：每个新增功能走 `changes/proposed/<id>/` proposal 流程
- proposal 模板见 `changes/_template/`
