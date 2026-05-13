"""Unit tests for pipeline/profile.py."""

import pandas as pd

from nextaiops_algo.core.table import FieldRole, Table, TableSchema
from nextaiops_algo.pipeline.profile import anomaly_segments, profile_table


def _make_table(with_label: bool = True) -> Table:
    """Create a table for profile tests."""
    data: dict[str, list[object]] = {
        "timestamp": list(range(8)),
        "value": [1.0, 2.0, None, 4.0, 10.0, 11.0, 6.0, 7.0],
        "value2": [2.0, 3.0, 4.0, 5.0, 20.0, 21.0, 8.0, 9.0],
    }
    roles = {
        "timestamp": FieldRole.TIMESTAMP,
        "value": FieldRole.METRIC,
        "value2": FieldRole.METRIC,
    }

    if with_label:
        data["is_anomaly"] = [0, 1, 1, 0, 1, 1, 1, 0]
        roles["is_anomaly"] = FieldRole.LABEL

    return Table(df=pd.DataFrame(data), schema=TableSchema(roles=roles))


def test_anomaly_segments_returns_inclusive_ranges() -> None:
    """anomaly_segments() returns contiguous inclusive label ranges."""
    assert anomaly_segments([0, 1, 1, 0, 1]) == [(1, 2), (4, 4)]
    assert anomaly_segments([1, 1, 0, 1]) == [(0, 1), (3, 3)]
    assert anomaly_segments([0, 0, 0]) == []


def test_profile_table_basic_shape_and_columns() -> None:
    """profile_table() summarizes rows, columns, and roles."""
    profile = profile_table(_make_table())

    assert profile.row_count == 8
    assert profile.column_count == 4
    assert profile.metric_columns == ("value", "value2")
    assert profile.timestamp_column == "timestamp"
    assert profile.label_column == "is_anomaly"


def test_profile_table_column_quality() -> None:
    """Column profiles include dtype, missing count, and unique values."""
    profile = profile_table(_make_table())
    value_profile = next(column for column in profile.columns if column.name == "value")

    assert value_profile.role == FieldRole.METRIC
    assert value_profile.missing_count == 1
    assert value_profile.missing_rate == 0.125
    assert value_profile.unique_count == 7


def test_profile_table_label_stats() -> None:
    """Label profile includes anomaly point and segment statistics."""
    profile = profile_table(_make_table())

    assert profile.label is not None
    assert profile.label.true_anomalies == 5
    assert profile.label.anomaly_rate == 0.625
    assert profile.label.segment_count == 2
    assert profile.label.longest_segment == 3


def test_profile_table_without_label_graceful_degradation() -> None:
    """Tables without LABEL return no label profile."""
    profile = profile_table(_make_table(with_label=False))

    assert profile.label_column is None
    assert profile.label is None
