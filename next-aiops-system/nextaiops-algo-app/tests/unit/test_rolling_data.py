import pandas as pd
import pytest

from nextaiops_algo.core.table import FieldRole, Table, TableSchema
from nextaiops_algo.pipeline.rolling_data import (
    SyntheticTimeConfig,
    build_day_partitions,
    cumulative_training_window,
    partition_tables,
    split_train_validate,
)


def _table(df: pd.DataFrame, roles: dict[str, FieldRole]) -> Table:
    return Table(df=df, schema=TableSchema(roles=roles))


def test_build_day_partitions_utc_and_seconds_milliseconds() -> None:
    df = pd.DataFrame(
        {
            "ts": [1714607999, 1714608000000, "2024-05-02T05:00:00+08:00"],
            "metric": [1.0, 2.0, 3.0],
            "label": [1, 0, 1],
        }
    )
    table = _table(df, {"ts": FieldRole.TIMESTAMP, "metric": FieldRole.METRIC, "label": FieldRole.LABEL})
    parts = build_day_partitions(table)
    assert [p.date.isoformat() for p in parts] == ["2024-05-01", "2024-05-02"]
    assert [p.row_count for p in parts] == [2, 1]


def test_build_day_partitions_parse_error_exclude() -> None:
    df = pd.DataFrame({"ts": ["bad", "2024-05-01T00:00:00Z"], "metric": [1.0, 2.0]})
    table = _table(df, {"ts": FieldRole.TIMESTAMP, "metric": FieldRole.METRIC})
    parts = build_day_partitions(table, on_timestamp_parse_error="exclude")
    assert len(parts) == 2
    assert any(p.exclusion_reason and p.exclusion_reason.value == "TIMESTAMP_PARSE_ERROR" for p in parts)


def test_synthetic_timestamp_and_split_guarantee() -> None:
    df = pd.DataFrame({"idx": [0, 1, 2, 3], "metric": [1.0, 2.0, 3.0, 4.0]})
    table = _table(df, {"idx": FieldRole.METRIC, "metric": FieldRole.METRIC})
    cfg = SyntheticTimeConfig(
        time_index_column="idx", synthetic_start_time="2024-01-01T00:00:00Z", synthetic_interval="1h"
    )
    parts = build_day_partitions(table, synthetic_time=cfg)
    assert len(parts) == 1


def test_synthetic_timestamp_invalid_interval_and_non_monotonic() -> None:
    df = pd.DataFrame({"idx": [1, 0], "metric": [1.0, 2.0]})
    table = _table(df, {"idx": FieldRole.METRIC, "metric": FieldRole.METRIC})
    with pytest.raises(ValueError):
        build_day_partitions(
            table,
            synthetic_time=SyntheticTimeConfig(
                time_index_column="idx", synthetic_start_time="2024-01-01T00:00:00Z", synthetic_interval="5x"
            ),
        )


def test_split_train_validate_same_timestamp_not_split_and_ratio_invalid() -> None:
    df = pd.DataFrame(
        {
            "ts": ["2024-05-01T00:00:00Z", "2024-05-01T00:00:00Z", "2024-05-02T00:00:00Z"],
            "metric": [1.0, 2.0, 3.0],
        }
    )
    table = _table(df, {"ts": FieldRole.TIMESTAMP, "metric": FieldRole.METRIC})
    with pytest.raises(ValueError):
        split_train_validate(table, ratio=1.0)

    train, validate = split_train_validate(table, ratio=0.5)
    assert len(train.df) == 2
    assert len(validate.df) == 1


def test_partition_tables_and_cumulative_window_and_cutoff_validation() -> None:
    df = pd.DataFrame(
        {
            "ts": ["2024-05-01T00:00:00Z", "2024-05-02T00:00:00Z"],
            "metric": [1.0, 2.0],
        }
    )
    table = _table(df, {"ts": FieldRole.TIMESTAMP, "metric": FieldRole.METRIC})
    parts = build_day_partitions(table)
    pmap = partition_tables(table, parts)
    merged = cumulative_training_window(pmap, "2024-05-01")
    assert len(merged.df) == 1
    with pytest.raises(ValueError):
        cumulative_training_window(pmap, "2024/05/01")


def test_build_day_partitions_threshold_range_validation() -> None:
    df = pd.DataFrame({"ts": ["2024-05-01T00:00:00Z"], "metric": [1.0]})
    table = _table(df, {"ts": FieldRole.TIMESTAMP, "metric": FieldRole.METRIC})
    with pytest.raises(ValueError):
        build_day_partitions(table, threshold=1.5)


def test_partition_tables_supports_synthetic_time() -> None:
    df = pd.DataFrame({"idx": [0, 1], "metric": [1.0, 2.0]})
    table = _table(df, {"idx": FieldRole.METRIC, "metric": FieldRole.METRIC})
    cfg = SyntheticTimeConfig(
        time_index_column="idx", synthetic_start_time="2024-01-01T00:00:00Z", synthetic_interval="24h"
    )
    parts = build_day_partitions(table, synthetic_time=cfg)
    pmap = partition_tables(table, parts, synthetic_time=cfg)
    assert sorted(pmap.keys()) == ["2024-01-01", "2024-01-02"]


def test_build_day_partitions_excludes_low_label_coverage() -> None:
    df = pd.DataFrame(
        {
            "ts": ["2024-05-01T00:00:00Z", "2024-05-01T01:00:00Z"],
            "metric": [1.0, 2.0],
            "label": [1, None],
        }
    )
    table = _table(df, {"ts": FieldRole.TIMESTAMP, "metric": FieldRole.METRIC, "label": FieldRole.LABEL})
    parts = build_day_partitions(table, threshold=0.75)
    assert len(parts) == 1
    assert parts[0].status.value == "excluded"
    assert parts[0].exclusion_reason is not None
    assert parts[0].exclusion_reason.value == "LOW_LABEL_COVERAGE"


def test_split_train_validate_enforces_time_boundary() -> None:
    df = pd.DataFrame(
        {
            "ts": [
                "2024-05-01T00:00:00Z",
                "2024-05-01T01:00:00Z",
                "2024-05-02T00:00:00Z",
                "2024-05-03T00:00:00Z",
            ],
            "metric": [1.0, 2.0, 3.0, 4.0],
        }
    )
    table = _table(df, {"ts": FieldRole.TIMESTAMP, "metric": FieldRole.METRIC})
    train, validate = split_train_validate(table, ratio=0.5)

    train_max = pd.to_datetime(train.df["ts"], utc=True).max()
    validate_min = pd.to_datetime(validate.df["ts"], utc=True).min()
    assert validate_min >= train_max


def test_cumulative_training_window_rejects_non_iso_partition_key() -> None:
    df = pd.DataFrame({"ts": ["2024-05-01T00:00:00Z"], "metric": [1.0]})
    table = _table(df, {"ts": FieldRole.TIMESTAMP, "metric": FieldRole.METRIC})
    with pytest.raises(ValueError):
        cumulative_training_window({"2024/05/01": table}, "2024-05-02")
