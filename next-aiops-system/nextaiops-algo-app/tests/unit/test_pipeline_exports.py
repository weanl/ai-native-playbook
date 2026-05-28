from nextaiops_algo.pipeline import (
    DayPartition,
    ExclusionReason,
    PartitionStatus,
    SyntheticTimeConfig,
    build_day_partitions,
    cumulative_training_window,
    partition_tables,
    split_train_validate,
)


def test_pipeline_exports_include_rolling_data_symbols() -> None:
    assert PartitionStatus.VALID.value == "valid"
    assert ExclusionReason.LOW_LABEL_COVERAGE.value == "LOW_LABEL_COVERAGE"
    assert DayPartition is not None
    assert SyntheticTimeConfig is not None
    assert callable(build_day_partitions)
    assert callable(partition_tables)
    assert callable(cumulative_training_window)
    assert callable(split_train_validate)
