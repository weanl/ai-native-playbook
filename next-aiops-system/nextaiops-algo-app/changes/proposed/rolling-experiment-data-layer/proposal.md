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

class DayPartition(BaseModel):
    date: str                    # YYYY-MM-DD
    row_count: int
    has_label: bool
    label_coverage: float | None # 有 label 时为 0.0~1.0，无 label 时为 None
    status: PartitionStatus
    exclusion_reason: str | None # 排除原因（schema 异常 / label coverage 不足）
```

### 核心函数

```python
def build_day_partitions(
    table: Table,
    date_column: str | None = None,
    label_coverage_threshold: float = 0.0,
) -> list[DayPartition]:
    """将 Table 按日期列切分为日分区。

    Args:
        table: 输入 Table，必须含 TIMESTAMP 列。
        date_column: 日期列名。None 时自动取 TIMESTAMP 角色列。
        label_coverage_threshold: label 覆盖率门槛，低于此值的分区标记 excluded。
            默认 0.0 表示只要有 label 列即可（允许全空 label 的分区）。

    Returns:
        按日期升序排列的 DayPartition 列表。

    Raises:
        SchemaValidationError: 无 TIMESTAMP 列、date_column 不存在。
    """
```

```python
def partition_tables(
    table: Table,
    partitions: list[DayPartition],
    date_column: str | None = None,
) -> dict[str, Table]:
    """将 Table 按日分区切分为 {date: Table} 映射。

    只返回 status=VALID 的分区。
    """
```

```python
def cumulative_training_window(
    partition_tables: dict[str, Table],
    cutoff_day: str,
) -> Table:
    """构建 <= cutoff_day 的累积训练窗口。

    Args:
        partition_tables: {date: Table} 映射（仅含 valid 分区）。
        cutoff_day: 截止日期 YYYY-MM-DD。

    Returns:
        合并后的 Table（按日期升序拼接）。

    Raises:
        ValueError: cutoff_day 之前无有效分区。
    """
```

```python
def split_train_validate(
    window: Table,
    ratio: float = 0.7,
) -> tuple[Table, Table]:
    """在训练窗口内切分 train / validate。

    复用现有 split_by_time 逻辑。
    """
```

### 数据质量检查规则

| 规则 | 触发条件 | 结果 |
|---|---|---|
| 无 TIMESTAMP 列 | Table 无 TIMESTAMP 角色 | 整体抛 SchemaValidationError |
| date_column 不存在 | 指定列不在 df 中 | 整体抛 SchemaValidationError |
| label coverage 不足 | 分区 label 非空率 < threshold | 分区标记 excluded |
| 分区行数 = 0 | 某日无数据 | 不产生分区（自然跳过） |

### 与现有模块的关系

- `read_to_table`：仍负责加载数据到 Table。滚动实验先加载再切分。
- `DatasetBundle`：多文件 bundle 场景不在 M2-025 处理，M2-026 引擎层负责。
- `split_by_time`：`split_train_validate` 内部复用其逻辑。
- `run_experiment`：不受影响，M2-025 不修改现有 pipeline 函数。

### 备选方案

**方案 B：在 core/ 新增 DayPartition**：拒绝。日分区是 pipeline 层概念，不属于算法 I/O 契约。
**方案 C：修改 Table 增加 partition 属性**：拒绝。破坏 Table 不可变契约。
**方案 D：用 DatasetBundle 表达日分区**：拒绝。DatasetBundle 语义是多文件集合，日分区是单文件按时间切分，概念不同。

## Acceptance Criteria
- [ ] `build_day_partitions` 可将含 timestamp 的 Table 切分为日分区列表
- [ ] 每个 DayPartition 有 date / row_count / has_label / label_coverage / status
- [ ] label coverage 不足的分区标记 excluded 并记录 exclusion_reason
- [ ] 无 TIMESTAMP 列时抛 SchemaValidationError
- [ ] `partition_tables` 返回 {date: Table}，仅含 valid 分区
- [ ] `cumulative_training_window` 对 cutoff day D 返回 <= D 的合并 Table
- [ ] cutoff_day 之前无有效分区时抛 ValueError
- [ ] `split_train_validate` 可按 ratio 切分 train / validate
- [ ] 不影响现有 `run_experiment` / `run_batch` / `DatasetBundle` 行为
- [ ] 不修改 `core/` 既有接口
- [ ] `make test` / `make lint` / `make smoke` 通过

## Related
- 范围锚点：`docs/PLAN.md` 中的 `M2-025: rolling-experiment-data-layer`
- 前置：M2-024（UI 设计，已完成）
- 后续：M2-026（滚动实验引擎，依赖本 proposal）
