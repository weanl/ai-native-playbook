"""Rolling experiment data-layer utilities for day partitioning and time-safe splits."""

from __future__ import annotations

import re
from datetime import date, datetime
from enum import StrEnum

import pandas as pd
from pydantic import BaseModel

from nextaiops_algo.core.table import FieldRole, Table, TableSchema


class PartitionStatus(StrEnum):
    """Status of a day partition after quality checks."""

    VALID = "valid"
    EXCLUDED = "excluded"


class ExclusionReason(StrEnum):
    """Reasons why a day partition can be excluded."""

    LOW_LABEL_COVERAGE = "LOW_LABEL_COVERAGE"
    TIMESTAMP_PARSE_ERROR = "TIMESTAMP_PARSE_ERROR"


class DayPartition(BaseModel):
    """Metadata for one UTC day partition."""

    date: date
    row_count: int
    has_label: bool
    label_coverage: float | None
    status: PartitionStatus
    exclusion_reason: ExclusionReason | None


class SyntheticTimeConfig(BaseModel):
    """Config to synthesize timestamps from an index-like column."""

    time_index_column: str
    synthetic_start_time: str
    synthetic_interval: str


_INTERVAL_PATTERN = re.compile(r"^(?P<n>[1-9]\d*)(?P<unit>s|min|h)$")


def _normalize_timestamps_to_utc(
    values: pd.Series,
    *,
    on_timestamp_parse_error: str,
) -> tuple[pd.Series, pd.Series]:
    if on_timestamp_parse_error not in {"raise", "exclude"}:
        raise ValueError("on_timestamp_parse_error must be one of: 'raise', 'exclude'")

    parsed = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns, UTC]")

    if pd.api.types.is_datetime64_any_dtype(values):
        parsed = pd.to_datetime(values, utc=True, errors="coerce")
        parse_error_mask = parsed.isna()
        if parse_error_mask.any() and on_timestamp_parse_error == "raise":
            invalid_count = int(parse_error_mask.sum())
            raise ValueError(
                f"Failed to parse {invalid_count} timestamp values. "
                "Set on_timestamp_parse_error='exclude' to skip invalid rows."
            )
        return parsed, parse_error_mask

    numeric = pd.to_numeric(values, errors="coerce")
    numeric_mask = numeric.notna()
    if numeric_mask.any():
        num_vals = numeric[numeric_mask].astype("float64")
        ms_mask = num_vals.abs() >= 1e12
        if ms_mask.any():
            parsed.loc[num_vals[ms_mask].index] = pd.to_datetime(
                num_vals[ms_mask], unit="ms", utc=True
            )
        if (~ms_mask).any():
            parsed.loc[num_vals[~ms_mask].index] = pd.to_datetime(
                num_vals[~ms_mask], unit="s", utc=True
            )

    non_numeric_mask = ~numeric_mask
    if non_numeric_mask.any():
        parsed.loc[non_numeric_mask] = pd.to_datetime(
            values[non_numeric_mask], errors="coerce", utc=True, format="mixed"
        )

    parse_error_mask = parsed.isna()
    if parse_error_mask.any() and on_timestamp_parse_error == "raise":
        invalid_count = int(parse_error_mask.sum())
        raise ValueError(
            f"Failed to parse {invalid_count} timestamp values. "
            "Set on_timestamp_parse_error='exclude' to skip invalid rows."
        )

    return parsed, parse_error_mask


def _build_synthetic_timestamps(table: Table, cfg: SyntheticTimeConfig) -> pd.Series:
    if cfg.time_index_column == "__row_index__":
        idx = pd.Series(range(len(table.df)), index=table.df.index, dtype="int64")
    elif cfg.time_index_column not in table.df.columns:
        raise ValueError(f"time_index_column '{cfg.time_index_column}' not found in table")
    else:
        idx = pd.to_numeric(table.df[cfg.time_index_column], errors="coerce")

    match = _INTERVAL_PATTERN.match(cfg.synthetic_interval)
    if not match:
        raise ValueError("synthetic_interval must match pattern Ns/Nmin/Nh (e.g. 30s, 5min, 1h)")

    unit_map = {"s": "s", "min": "min", "h": "h"}
    delta = pd.to_timedelta(int(match.group("n")), unit=unit_map[match.group("unit")])

    start = pd.to_datetime(cfg.synthetic_start_time, utc=True, errors="coerce")
    if pd.isna(start):
        raise ValueError("synthetic_start_time must be a parseable datetime")

    if idx.isna().any():
        raise ValueError("time_index_column must be numeric and non-null")
    if not idx.is_monotonic_increasing:
        raise ValueError("time_index_column must be monotonic increasing")

    idx_int = idx.astype("int64")
    if not (idx_int == idx).all():
        raise ValueError("time_index_column values must be integers")

    return pd.Series(start + idx_int * delta, index=table.df.index, dtype="datetime64[ns, UTC]")


def build_day_partitions(
    table: Table,
    date_column: str | None = None,
    threshold: float | None = None,
    synthetic_time: SyntheticTimeConfig | None = None,
    on_timestamp_parse_error: str = "raise",
) -> list[DayPartition]:
    """Build UTC day partitions with status and quality metadata."""
    label = table.labels()
    if threshold is not None and not (0 <= threshold <= 1):
        raise ValueError("threshold must be in [0, 1]")

    if date_column is not None:
        if date_column not in table.df.columns:
            raise ValueError(f"date_column '{date_column}' not found in table")
        raw_ts = table.df[date_column]
    else:
        ts = table.timestamps()
        if ts is not None:
            raw_ts = ts
        elif synthetic_time is not None:
            raw_ts = _build_synthetic_timestamps(table, synthetic_time)
        else:
            raise ValueError("No timestamp column found; provide synthetic_time for index-only datasets")

    normalized, parse_error_mask = _normalize_timestamps_to_utc(
        raw_ts, on_timestamp_parse_error=on_timestamp_parse_error
    )
    working = table.df.copy()
    working["__utc_ts"] = normalized
    working["__parse_error"] = parse_error_mask

    partitions: list[DayPartition] = []
    valid_rows = working[~working["__utc_ts"].isna()].copy()
    if not valid_rows.empty:
        valid_rows["__day"] = valid_rows["__utc_ts"].dt.date
        for day, g in valid_rows.groupby("__day", sort=True):
            coverage = None
            has_label = label is not None
            if has_label:
                assert label is not None
                coverage = float(g[label.name].notna().mean())
            status = PartitionStatus.VALID
            reason = None
            if threshold is not None and has_label and coverage is not None and coverage < threshold:
                status = PartitionStatus.EXCLUDED
                reason = ExclusionReason.LOW_LABEL_COVERAGE
            partitions.append(
                DayPartition(
                    date=day,
                    row_count=len(g),
                    has_label=has_label,
                    label_coverage=coverage,
                    status=status,
                    exclusion_reason=reason,
                )
            )

    if parse_error_mask.any() and on_timestamp_parse_error == "exclude":
        partitions.append(
            DayPartition(
                date=date.min,
                row_count=int(parse_error_mask.sum()),
                has_label=label is not None,
                label_coverage=None,
                status=PartitionStatus.EXCLUDED,
                exclusion_reason=ExclusionReason.TIMESTAMP_PARSE_ERROR,
            )
        )

    return partitions


def partition_tables(
    table: Table,
    partitions: list[DayPartition],
    date_column: str | None = None,
    synthetic_time: SyntheticTimeConfig | None = None,
) -> dict[str, Table]:
    """Materialize tables for valid day partitions only."""
    if date_column is not None:
        raw_ts = table.df[date_column]
    else:
        raw_ts = table.timestamps()
        if raw_ts is None and synthetic_time is not None:
            raw_ts = _build_synthetic_timestamps(table, synthetic_time)
    if raw_ts is None:
        raise ValueError("partition_tables requires timestamp/date_column or synthetic_time")
    normalized, _ = _normalize_timestamps_to_utc(raw_ts, on_timestamp_parse_error="raise")
    day_series = normalized.dt.date

    results: dict[str, Table] = {}
    for partition in partitions:
        if partition.status != PartitionStatus.VALID:
            continue
        key = partition.date.isoformat()
        mask = day_series == partition.date
        part_df = table.df.loc[mask].copy()
        roles = dict(table.schema.roles)
        if synthetic_time is not None and table.timestamps() is None:
            part_df["__synthetic_timestamp"] = normalized.loc[mask].values
            roles["__synthetic_timestamp"] = FieldRole.TIMESTAMP
        results[key] = Table(df=part_df, schema=TableSchema(roles=roles))
    return results


def cumulative_training_window(partitioned_tables: dict[str, Table], cutoff_day: str) -> Table:
    """Merge day tables whose day <= cutoff_day (inclusive)."""
    try:
        cutoff = datetime.strptime(cutoff_day, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("cutoff_day must be in YYYY-MM-DD format, e.g. 2026-01-31") from exc

    dated_keys: list[tuple[str, date]] = []
    for key in partitioned_tables:
        try:
            key_day = datetime.strptime(key, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(f"Partition key '{key}' must be in YYYY-MM-DD format") from exc
        dated_keys.append((key, key_day))

    selected_keys = sorted([k for k, k_day in dated_keys if k_day <= cutoff])
    if not selected_keys:
        raise ValueError(f"No partitions found on or before cutoff_day={cutoff_day}")

    schema = TableSchema(roles=dict(partitioned_tables[selected_keys[0]].schema.roles))
    merged = pd.concat([partitioned_tables[k].df for k in selected_keys], ignore_index=True)
    return Table(df=merged, schema=schema)


def split_train_validate(window: Table, ratio: float) -> tuple[Table, Table]:
    """Split by timestamp boundary with same-timestamp non-splitting guarantees."""
    if not (0 < ratio < 1):
        raise ValueError("ratio must be in (0, 1)")
    ts = window.timestamps()
    if ts is None:
        raise ValueError("split_train_validate requires a TIMESTAMP column")

    normalized, _ = _normalize_timestamps_to_utc(ts, on_timestamp_parse_error="raise")
    order = normalized.sort_values(kind="stable").index
    n = len(order)
    if n < 2:
        raise ValueError("split_train_validate requires at least 2 rows")

    boundary = int(n * ratio)
    boundary = max(1, min(boundary, n - 1))
    cutoff_ts = normalized.loc[order[boundary - 1]]

    train_mask = normalized <= cutoff_ts
    validate_mask = normalized > cutoff_ts

    if not validate_mask.any() or not train_mask.any():
        raise ValueError("Cannot split without crossing timestamp groups; provide a different ratio")

    train_df = window.df.loc[train_mask].copy()
    validate_df = window.df.loc[validate_mask].copy()

    train = Table(df=train_df, schema=TableSchema(roles=dict(window.schema.roles)))
    validate = Table(df=validate_df, schema=TableSchema(roles=dict(window.schema.roles)))
    return train, validate
