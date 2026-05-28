# Proposal ID: M2-025

## Title
滚动实验数据层：日分区 + 累积训练窗口 + 数据质量检查

## Motivation
- **Why**: M2 滚动实验 MVP 需要将一次导入的多天数据按日切分为分区，对每个 cutoff day 构建累积训练窗口，并在窗口内切分 train/validate。当前 `Table` / `DatasetBundle` / `split_by_time` 不具备日分区与累积窗口能力。
- **Impact**: 为 M2-026 滚动实验引擎提供数据层基础，使引擎能按日循环驱动训练与推理。

## Scope
- **Modules affected**: pipeline
- **Files changed**:
  - `src/nextaiops_algo/pipeline/rolling_data.py` ← 新增
  - `tests/unit/test_rolling_data.py` ← 新增
  - `tests/integration/test_rolling_data_e2e.py` ← 新增
- **Dependencies**: 无新增依赖

## Design

### 数据模型

放在 `pipeline/` 可变层，不修改 `core/`：

```python
class PartitionStatus(StrEnum):
    VALID = "valid"
    EXCLUDED = "excluded"

class ExclusionReason(StrEnum):
    LOW_LABEL_COVERAGE = "LOW_LABEL_COVERAGE"
    TIMESTAMP_PARSE_ERROR = "TIMESTAMP_PARSE_ERROR"

class DayPartition(BaseModel):
    date: date                   # 序列化为 YYYY-MM-DD
    row_count: int
    has_label: bool
    label_coverage: float | None # 有 label 时为 0.0~1.0，无 label 时为 None
    status: PartitionStatus
    exclusion_reason: ExclusionReason | None
```

### 时间规范化策略（新增，阻塞项）

- 所有分区前统一做 timestamp 规范化：**先转 UTC，再按 UTC date 分区**。
- 数值 timestamp 推断规则：`abs(value) >= 1e12` 视为毫秒，否则视为秒。
- 解析失败策略：
  - 默认 fail-fast：抛 `SchemaValidationError` 并包含列名/样本值；
  - 可选模式（由调用方显式开启）：将受影响分区标记 `EXCLUDED`，`exclusion_reason=TIMESTAMP_PARSE_ERROR`。

### 无原生时间戳数据的适配（新增）

为仅有编号（`id/step/index`）的数据提供 synthetic timestamp 模式：

```python
class SyntheticTimeConfig(BaseModel):
    time_index_column: str
    synthetic_start_time: str   # ISO-8601
    synthetic_interval: str     # e.g. 5s/1min/1h
```

- 启用条件：输入无 `TIMESTAMP` 且 `SyntheticTimeConfig` 完整提供。
- 生成规则：`ts(i) = start_time + offset(i) * interval`（`offset(i)` 来自行号或 `time_index_column` 数值）。
- 约束：`interval > 0`、`start_time` 可解析、`time_index_column` 单调非降；否则 fail-fast。
- 优先级：若输入已有真实 `TIMESTAMP`，默认优先真实时间戳。

### 核心函数

```python
def build_day_partitions(
    table: Table,
    date_column: str | None = None,
    label_coverage_threshold: float = 0.0,
    synthetic_time: SyntheticTimeConfig | None = None,
) -> list[DayPartition]:
    """将 Table 切分为日分区（UTC date）。

    Raises:
        SchemaValidationError: 时间列缺失/无法解析/配置非法。
    """
```

```python
def partition_tables(
    table: Table,
    partitions: list[DayPartition],
    date_column: str | None = None,
) -> dict[str, Table]:
    """将 Table 按日分区切分为 {date: Table} 映射，仅返回 VALID 分区。"""
```

```python
def cumulative_training_window(
    partition_tables: dict[str, Table],
    cutoff_day: str,
) -> Table:
    """构建 <= cutoff_day 的累积训练窗口。"""
```

```python
def split_train_validate(
    window: Table,
    ratio: float = 0.7,
) -> tuple[Table, Table]:
    """在训练窗口内按时间切分 train/validate。"""
```

### split_train_validate 边界语义（新增，阻塞项）

- `ratio` 必须满足 `(0, 1)`，否则抛 `ValueError`。
- 切分按“时间边界”而非纯行比例：验证集最早 timestamp 必须 `>=` 训练集最晚 timestamp。
- 同一 timestamp 的多行不得跨 train/validate 两侧（避免泄漏）。
- 样本过少无法满足最小切分时抛 `ValueError`（包含最小样本要求说明）。

### 与现有模块的关系

- `read_to_table`：仍负责加载数据到 Table。滚动实验先加载再切分。
- `DatasetBundle`：多文件 bundle 场景不在 M2-025 处理，M2-026 引擎层负责。
- `split_by_time`：`split_train_validate` 复用其实现思想，但新增边界保护与参数校验。
- `run_experiment`：不受影响，M2-025 不修改现有 pipeline 函数。

### 备选方案

**方案 B：在 core/ 新增 DayPartition**：拒绝。日分区是 pipeline 层概念，不属于算法 I/O 契约。
**方案 C：修改 Table 增加 partition 属性**：拒绝。破坏 Table 不可变契约。
**方案 D：用 DatasetBundle 表达日分区**：拒绝。DatasetBundle 语义是多文件集合，日分区是单文件按时间切分，概念不同。

## Acceptance Criteria
- [ ] `build_day_partitions` 对真实 timestamp 数据按 **UTC date** 稳定分区
- [ ] 数值 timestamp（秒/毫秒）与字符串 timestamp 在 UTC 归一后分区结果一致
- [ ] 无原生 timestamp 时，提供 `SyntheticTimeConfig` 可成功分区；配置缺失/非法时抛 `SchemaValidationError`
- [ ] 每个 DayPartition 包含 `date/row_count/has_label/label_coverage/status/exclusion_reason`
- [ ] label coverage 不足的分区标记 `EXCLUDED` 且 `exclusion_reason=LOW_LABEL_COVERAGE`
- [ ] `partition_tables` 返回 `{date: Table}` 且仅含 `VALID` 分区
- [ ] `cumulative_training_window` 对 cutoff day `D` 返回 `<= D` 的合并 Table；无有效分区时抛 `ValueError`
- [ ] `split_train_validate` 在 `ratio in (0,1)` 时成功切分；非法 ratio 抛 `ValueError`
- [ ] train/validate 满足时间边界：`min(validate.ts) >= max(train.ts)`，且同 timestamp 不跨集合
- [ ] 不影响现有 `run_experiment` / `run_batch` / `DatasetBundle` 行为（相关测试不回归）
- [ ] 不修改 `core/` 既有接口

## Related
- 范围锚点：`docs/PLAN.md` 中的 `M2-025: rolling-experiment-data-layer`
- 前置：M2-024（UI 设计，已完成）
- 后续：M2-026（滚动实验引擎，依赖本 proposal）
