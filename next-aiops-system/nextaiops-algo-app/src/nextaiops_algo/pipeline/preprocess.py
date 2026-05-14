"""Preprocessing utilities for data → Table conversion and splitting."""

from collections.abc import Sequence
from pathlib import Path

from nextaiops_algo.core.table import Table
from nextaiops_algo.datasets.loaders import (
    read_csv_to_table as _read_csv_to_table,
)
from nextaiops_algo.datasets.loaders import (
    read_to_table as _read_to_table,
)
from nextaiops_algo.pipeline.dataset_bundle import (
    DatasetBundle,
    load_dataset_bundle,
    load_dataset_bundle_from_zip,
)


def read_csv_to_table(path: Path, dataset_version: str | None = None) -> Table:
    """Read CSV file and infer column roles to create a Table.

    Backward-compatible wrapper — delegates to datasets.loaders.read_csv_to_table.

    Args:
        path: Path to the CSV file.
        dataset_version: Unused in M1 (kept for backward compat).

    Returns:
        Table with inferred schema.
    """
    return _read_csv_to_table(path)


def read_to_table(path_or_name: str | Path) -> Table:
    """Unified entry: load data from path or builtin dataset name.

    Delegates to datasets.loaders.read_to_table.

    Args:
        path_or_name: File path (.csv/.out/.npy/.npz) or builtin dataset name.

    Returns:
        Table loaded from the appropriate source.
    """
    return _read_to_table(path_or_name)


def read_dataset_bundle(
    paths: Sequence[str | Path],
    dataset_id: str | None = None,
) -> DatasetBundle:
    """Load multiple files as one schema-consistent DatasetBundle."""
    return load_dataset_bundle(paths, dataset_id=dataset_id)


def read_dataset_bundle_from_zip(
    zip_path: Path,
    extract_dir: Path,
    dataset_id: str | None = None,
) -> DatasetBundle:
    """Load supported files from a zip archive as a DatasetBundle."""
    return load_dataset_bundle_from_zip(zip_path, extract_dir=extract_dir, dataset_id=dataset_id)


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
