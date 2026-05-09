"""Preprocessing utilities for CSV → Table conversion and data splitting."""

import logging
from pathlib import Path

import pandas as pd

from nextaiops_algo.core.exceptions import SchemaValidationError
from nextaiops_algo.core.table import FieldRole, Table, TableSchema

logger = logging.getLogger(__name__)

# Column name patterns for role inference (case-insensitive)
TIMESTAMP_PATTERNS = {"timestamp", "time", "ts", "datetime"}
LABEL_PATTERNS = {"label", "anomaly", "is_anomaly", "y"}


def read_csv_to_table(path: Path, dataset_version: str | None = None) -> Table:
    """Read CSV file and infer column roles to create a Table.

    Inference rules (AGENTS.md §9.4):
    - TIMESTAMP: column name matches timestamp/time/ts/datetime (case-insensitive)
    - LABEL: column name matches label/anomaly/is_anomaly/y (case-insensitive)
    - METRIC: other numeric columns
    - Non-numeric columns: skipped with WARNING log

    Args:
        path: Path to the CSV file.
        dataset_version: Optional version identifier. If None, uses file hash.

    Returns:
        Table with inferred schema.

    Raises:
        SchemaValidationError: If no METRIC columns found or multiple TIMESTAMP/LABEL matches.
        FileNotFoundError: If CSV file does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    df = pd.read_csv(path)

    roles: dict[str, FieldRole] = {}
    timestamp_count = 0
    label_count = 0

    for col in df.columns:
        col_lower = col.lower()

        # Check TIMESTAMP patterns
        if col_lower in TIMESTAMP_PATTERNS:
            roles[col] = FieldRole.TIMESTAMP
            timestamp_count += 1
            continue

        # Check LABEL patterns
        if col_lower in LABEL_PATTERNS:
            roles[col] = FieldRole.LABEL
            label_count += 1
            continue

        # Check if numeric for METRIC
        if pd.api.types.is_numeric_dtype(df[col]):
            roles[col] = FieldRole.METRIC
        else:
            # Non-numeric, skip with warning
            logger.warning(
                f"Skipping non-numeric column '{col}' in CSV '{path.name}'. "
                f"M1 will support explicit schema override."
            )

    # Validate constraints
    if timestamp_count > 1:
        raise SchemaValidationError(
            f"Found {timestamp_count} TIMESTAMP columns, max allowed is 1",
            context={"timestamp_columns": [c for c, r in roles.items() if r == FieldRole.TIMESTAMP]},
        )

    if label_count > 1:
        raise SchemaValidationError(
            f"Found {label_count} LABEL columns, max allowed is 1",
            context={"label_columns": [c for c, r in roles.items() if r == FieldRole.LABEL]},
        )

    metric_cols = [c for c, r in roles.items() if r == FieldRole.METRIC]
    if len(metric_cols) == 0:
        raise SchemaValidationError(
            "No METRIC columns found in CSV. At least 1 numeric column required.",
            context={"file": str(path), "columns": list(df.columns)},
        )

    schema = TableSchema(roles=roles)
    return Table(df=df, schema=schema)


def split_by_time(table: Table, ratio: float = 0.7) -> tuple[Table, Table]:
    """Split Table by time order (first ratio% as train, rest as test).

    Args:
        table: Input Table to split.
        ratio: Fraction of data for training (0.0 to 1.0). Default 0.7.

    Returns:
        Tuple of (train_table, test_table), both with same schema as input.

    Raises:
        ValueError: If ratio is not between 0 and 1.
    """
    if not 0.0 < ratio < 1.0:
        raise ValueError(f"Split ratio must be between 0 and 1, got {ratio}")

    n_rows = len(table.df)
    split_idx = int(n_rows * ratio)

    train_df = table.df.iloc[:split_idx].copy()
    test_df = table.df.iloc[split_idx:].copy()

    # Both tables share the same schema
    return (
        Table(df=train_df, schema=table.schema),
        Table(df=test_df, schema=table.schema),
    )
