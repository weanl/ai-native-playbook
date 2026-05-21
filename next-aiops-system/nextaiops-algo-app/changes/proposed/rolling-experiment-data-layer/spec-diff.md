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
```

## After

新增数据层能力：

```text
build_day_partitions(table, date_column?, threshold?) → list[DayPartition]
partition_tables(table, partitions, date_column?) → dict[str, Table]
cumulative_training_window(partition_tables, cutoff_day) → Table
split_train_validate(window, ratio) → (train, validate)
```

### 新增数据模型

```python
class PartitionStatus(StrEnum):
    VALID = "valid"
    EXCLUDED = "excluded"

class DayPartition(BaseModel):
    date: str                    # YYYY-MM-DD
    row_count: int
    has_label: bool
    label_coverage: float | None
    status: PartitionStatus
    exclusion_reason: str | None
```

## Diff Summary

- **Added**: `DayPartition` / `PartitionStatus` 数据模型
- **Added**: `build_day_partitions` / `partition_tables` / `cumulative_training_window` / `split_train_validate` 函数
- **Removed**: 无
- **Changed**: 无

## Breaking Changes

无。新增文件 `pipeline/rolling_data.py`，不修改任何既有接口。

## Compatibility

- **Backward compatible**: Yes
- **Version impact**: M2（不影响 M0/M1 既有行为）
