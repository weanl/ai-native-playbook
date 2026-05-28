# Spec Diff - Proposal ID: M2-025

## Before

当前数据层只有以下能力：

```text
read_to_table(path_or_name) → Table
split_by_time(table, ratio) → (train, test)
DatasetBundle：多文件集合，schema 一致性校验
```

不支持：

```text
按日切分数据
累积训练窗口
日分区质量检查
无时间戳数据的滚动适配
```

## After

新增数据层能力：

```text
build_day_partitions(table, date_column?, threshold?, synthetic_time?) → list[DayPartition]
partition_tables(table, partitions, date_column?) → dict[str, Table]
cumulative_training_window(partition_tables, cutoff_day) → Table
split_train_validate(window, ratio) → (train, validate)
```

### 新增数据模型

```python
class PartitionStatus(StrEnum):
    VALID = "valid"
    EXCLUDED = "excluded"

class ExclusionReason(StrEnum):
    LOW_LABEL_COVERAGE = "LOW_LABEL_COVERAGE"
    TIMESTAMP_PARSE_ERROR = "TIMESTAMP_PARSE_ERROR"

class DayPartition(BaseModel):
    date: date
    row_count: int
    has_label: bool
    label_coverage: float | None
    status: PartitionStatus
    exclusion_reason: ExclusionReason | None

class SyntheticTimeConfig(BaseModel):
    time_index_column: str
    synthetic_start_time: str
    synthetic_interval: str
```

### 新增规则约束

- 时间规范化：先转 UTC，再按 UTC date 分区。
- 数值时间戳：`abs(v) >= 1e12` 判定为毫秒，否则秒。
- split 边界：`ratio in (0,1)`；同 timestamp 不跨集合；`min(validate.ts) >= max(train.ts)`。
- 无 timestamp 适配：支持 `SyntheticTimeConfig` 生成逻辑时间。

## Diff Summary

- **Added**: `DayPartition` / `PartitionStatus` / `ExclusionReason` / `SyntheticTimeConfig`
- **Added**: `build_day_partitions` / `partition_tables` / `cumulative_training_window` / `split_train_validate`
- **Added**: UTC 归一、秒毫秒识别、split 边界与 synthetic timestamp 规则
- **Removed**: 无
- **Changed**: 无

## Breaking Changes

无。新增文件 `pipeline/rolling_data.py`，不修改任何既有接口。

## Compatibility

- **Backward compatible**: Yes
- **Version impact**: M2（不影响 M0/M1 既有行为）
