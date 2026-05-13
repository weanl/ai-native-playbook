"""Data profiling helpers for Table preview."""

from __future__ import annotations

from dataclasses import dataclass

from nextaiops_algo.core.table import FieldRole, Table


@dataclass(frozen=True)
class ColumnProfile:
    """Profile of one table column."""

    name: str
    role: FieldRole
    dtype: str
    missing_count: int
    missing_rate: float
    unique_count: int


@dataclass(frozen=True)
class LabelProfile:
    """Profile of ground-truth anomaly labels."""

    true_anomalies: int
    anomaly_rate: float
    segment_count: int
    longest_segment: int


@dataclass(frozen=True)
class TableProfile:
    """Profile summary for a Table."""

    row_count: int
    column_count: int
    metric_columns: tuple[str, ...]
    timestamp_column: str | None
    label_column: str | None
    columns: tuple[ColumnProfile, ...]
    label: LabelProfile | None


def profile_table(table: Table) -> TableProfile:
    """Build a lightweight profile for a Table.

    Args:
        table: Input table to profile.

    Returns:
        Structured profile with column quality and label distribution.
    """
    row_count = len(table.df)
    column_profiles: list[ColumnProfile] = []

    for column, role in table.schema.roles.items():
        series = table.df[column]
        missing_count = int(series.isna().sum())
        missing_rate = missing_count / row_count if row_count > 0 else 0.0
        column_profiles.append(
            ColumnProfile(
                name=column,
                role=role,
                dtype=str(series.dtype),
                missing_count=missing_count,
                missing_rate=float(missing_rate),
                unique_count=int(series.nunique(dropna=True)),
            )
        )

    timestamp_columns = table.schema.columns_of(FieldRole.TIMESTAMP)
    label_columns = table.schema.columns_of(FieldRole.LABEL)

    return TableProfile(
        row_count=row_count,
        column_count=len(table.df.columns),
        metric_columns=tuple(table.schema.columns_of(FieldRole.METRIC)),
        timestamp_column=timestamp_columns[0] if timestamp_columns else None,
        label_column=label_columns[0] if label_columns else None,
        columns=tuple(column_profiles),
        label=_profile_labels(table),
    )


def anomaly_segments(labels: list[int]) -> list[tuple[int, int]]:
    """Return contiguous anomaly segments as inclusive index ranges.

    Args:
        labels: Point-wise labels where 1 means anomaly.

    Returns:
        List of ``(start, end)`` inclusive index ranges.
    """
    segments: list[tuple[int, int]] = []
    start: int | None = None

    for index, value in enumerate(labels):
        if value == 1 and start is None:
            start = index
        elif value != 1 and start is not None:
            segments.append((start, index - 1))
            start = None

    if start is not None:
        segments.append((start, len(labels) - 1))

    return segments


def _profile_labels(table: Table) -> LabelProfile | None:
    """Profile labels when the table has a LABEL column."""
    labels = table.labels()
    if labels is None:
        return None

    label_values = [int(value) for value in labels.fillna(0).tolist()]
    row_count = len(label_values)
    true_anomalies = sum(1 for value in label_values if value == 1)
    segments = anomaly_segments(label_values)
    longest_segment = max((end - start + 1 for start, end in segments), default=0)

    return LabelProfile(
        true_anomalies=true_anomalies,
        anomaly_rate=true_anomalies / row_count if row_count > 0 else 0.0,
        segment_count=len(segments),
        longest_segment=longest_segment,
    )
