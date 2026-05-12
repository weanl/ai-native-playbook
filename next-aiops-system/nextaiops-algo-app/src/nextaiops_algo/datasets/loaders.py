"""Dataset loaders for various input formats → Table conversion."""

from pathlib import Path

import numpy as np
import pandas as pd

from nextaiops_algo.core.exceptions import SchemaValidationError
from nextaiops_algo.core.table import FieldRole, Table, TableSchema

# Column name patterns for CSV role inference (case-insensitive)
TIMESTAMP_PATTERNS = {"timestamp", "time", "ts", "datetime"}
LABEL_PATTERNS = {"label", "anomaly", "is_anomaly", "y"}


def read_csv_to_table(path: Path) -> Table:
    """Read CSV file and infer column roles to create a Table.

    Inference rules (AGENTS.md §9.4):
    - TIMESTAMP: column name matches timestamp/time/ts/datetime (case-insensitive)
    - LABEL: column name matches label/anomaly/is_anomaly/y (case-insensitive)
    - METRIC: other numeric columns
    - Non-numeric columns: skipped

    Args:
        path: Path to the CSV file.

    Returns:
        Table with inferred schema.

    Raises:
        SchemaValidationError: If no METRIC columns or invalid role counts.
        FileNotFoundError: If CSV file does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        raise SchemaValidationError(
            "CSV file is empty — no data rows",
            context={"file": str(path)},
        ) from None
    if len(df) == 0:
        raise SchemaValidationError(
            "CSV file is empty — no data rows",
            context={"file": str(path)},
        )

    roles: dict[str, FieldRole] = {}
    timestamp_count = 0
    label_count = 0

    for col in df.columns:
        col_lower = col.lower()
        if col_lower in TIMESTAMP_PATTERNS:
            roles[col] = FieldRole.TIMESTAMP
            timestamp_count += 1
            continue
        if col_lower in LABEL_PATTERNS:
            roles[col] = FieldRole.LABEL
            label_count += 1
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            roles[col] = FieldRole.METRIC

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
            "No METRIC columns found. At least 1 numeric column required.",
            context={"file": str(path), "columns": list(df.columns)},
        )

    # Only keep columns with assigned roles
    df = df[[c for c in df.columns if c in roles]]
    schema = TableSchema(roles=roles)
    return Table(df=df, schema=schema)


def read_tsbuad_out_to_table(path: Path) -> Table:
    """Read TSB-UAD .out file (two columns: value + label) into a Table.

    TSB-UAD .out format:
    - No header row
    - Column 1: value (METRIC)
    - Column 2: is_anomaly (LABEL, 0/1)
    - No timestamp

    Args:
        path: Path to the .out file.

    Returns:
        Table with value as METRIC and is_anomaly as LABEL.

    Raises:
        SchemaValidationError: If file is not 2-column format.
        FileNotFoundError: If file does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f".out file not found: {path}")

    try:
        df = pd.read_csv(path, sep=r"\s+", header=None)
    except pd.errors.EmptyDataError:
        raise SchemaValidationError(
            ".out file is empty — no data rows",
            context={"file": str(path)},
        ) from None

    if df.shape[1] != 2:
        raise SchemaValidationError(
            f".out file must have exactly 2 columns (value, label), got {df.shape[1]}",
            context={"file": str(path), "column_count": df.shape[1]},
        )

    if len(df) == 0:
        raise SchemaValidationError(
            ".out file is empty — no data rows",
            context={"file": str(path)},
        )

    df.columns = ["value", "is_anomaly"]
    roles = {"value": FieldRole.METRIC, "is_anomaly": FieldRole.LABEL}
    schema = TableSchema(roles=roles)
    return Table(df=df, schema=schema)


def read_npy_to_table(
    data_path: Path,
    label_path: Path | None = None,
) -> Table:
    """Read .npy file(s) into a Table.

    Args:
        data_path: Path to data .npy file. Shape (N,) for single metric,
            (N, features) for multi-metric.
        label_path: Optional path to label .npy file. Shape (N,).

    Returns:
        Table with metric columns and optional label column.
        No timestamp (npy format has no time info).

    Raises:
        SchemaValidationError: If shapes are incompatible.
        FileNotFoundError: If file does not exist.
    """
    if not data_path.exists():
        raise FileNotFoundError(f"Data .npy file not found: {data_path}")

    data = np.load(data_path)

    if data.ndim == 1:
        df = pd.DataFrame({"metric_0": data})
        roles: dict[str, FieldRole] = {"metric_0": FieldRole.METRIC}
    elif data.ndim == 2:
        col_names = [f"metric_{i}" for i in range(data.shape[1])]
        df = pd.DataFrame(data, columns=col_names)
        roles = dict.fromkeys(col_names, FieldRole.METRIC)
    else:
        raise SchemaValidationError(
            f".npy data must be 1D or 2D array, got {data.ndim}D",
            context={"file": str(data_path), "shape": data.shape},
        )

    if len(df) == 0:
        raise SchemaValidationError(
            ".npy data is empty — zero rows",
            context={"file": str(data_path)},
        )

    if label_path is not None:
        if not label_path.exists():
            raise FileNotFoundError(f"Label .npy file not found: {label_path}")
        labels = np.load(label_path)
        if labels.shape[0] != len(df):
            raise SchemaValidationError(
                f"Label length ({labels.shape[0]}) != data length ({len(df)})",
                context={"data_file": str(data_path), "label_file": str(label_path)},
            )
        df["is_anomaly"] = labels
        roles["is_anomaly"] = FieldRole.LABEL

    schema = TableSchema(roles=roles)
    return Table(df=df, schema=schema)


def read_npz_to_table(path: Path) -> Table:
    """Read .npz file into a Table.

    Expected keys:
    - 'data': required, shape (N,) or (N, features)
    - 'label': optional, shape (N,)
    - 'timestamp': optional, shape (N,)

    Args:
        path: Path to the .npz file.

    Returns:
        Table with metric columns, optional label and timestamp.

    Raises:
        SchemaValidationError: If required keys missing or shapes incompatible.
        FileNotFoundError: If file does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f".npz file not found: {path}")

    npz = np.load(path)

    if "data" not in npz:
        raise SchemaValidationError(
            ".npz file must contain 'data' key",
            context={"file": str(path), "available_keys": list(npz.keys())},
        )

    data = npz["data"]
    roles: dict[str, FieldRole] = {}

    if data.ndim == 1:
        df = pd.DataFrame({"metric_0": data})
        roles["metric_0"] = FieldRole.METRIC
    elif data.ndim == 2:
        col_names = [f"metric_{i}" for i in range(data.shape[1])]
        df = pd.DataFrame(data, columns=col_names)
        roles = dict.fromkeys(col_names, FieldRole.METRIC)
    else:
        raise SchemaValidationError(
            f".npz 'data' must be 1D or 2D, got {data.ndim}D",
            context={"file": str(path), "shape": data.shape},
        )

    if len(df) == 0:
        raise SchemaValidationError(
            ".npz data is empty",
            context={"file": str(path)},
        )

    if "label" in npz:
        labels = npz["label"]
        if labels.shape[0] != len(df):
            raise SchemaValidationError(
                f"Label length ({labels.shape[0]}) != data length ({len(df)})",
                context={"file": str(path)},
            )
        df["is_anomaly"] = labels
        roles["is_anomaly"] = FieldRole.LABEL

    if "timestamp" in npz:
        ts = npz["timestamp"]
        if ts.shape[0] != len(df):
            raise SchemaValidationError(
                f"Timestamp length ({ts.shape[0]}) != data length ({len(df)})",
                context={"file": str(path)},
            )
        df["timestamp"] = ts
        roles["timestamp"] = FieldRole.TIMESTAMP

    schema = TableSchema(roles=roles)
    return Table(df=df, schema=schema)


def read_to_table(path_or_name: str | Path) -> Table:
    """Unified entry: load data from path or builtin dataset name.

    Dispatch order:
    1. If name matches builtin registry → load_builtin(name)
    2. Suffix .csv → read_csv_to_table
    3. Suffix .out → read_tsbuad_out_to_table
    4. Suffix .npy → read_npy_to_table
    5. Suffix .npz → read_npz_to_table
    6. Other → raise SchemaValidationError

    Args:
        path_or_name: File path or builtin dataset name.

    Returns:
        Table loaded from the appropriate source.

    Raises:
        SchemaValidationError: If format unrecognized or data invalid.
        FileNotFoundError: If file does not exist.
    """
    from nextaiops_algo.datasets.registry import BUILTIN_REGISTRY

    name = str(path_or_name)

    # Check builtin first
    if name in BUILTIN_REGISTRY:
        return BUILTIN_REGISTRY[name].load()

    path = Path(name)
    suffix = path.suffix.lower()

    if suffix == ".csv":
        return read_csv_to_table(path)
    if suffix == ".out":
        return read_tsbuad_out_to_table(path)
    if suffix == ".npy":
        return read_npy_to_table(path)
    if suffix == ".npz":
        return read_npz_to_table(path)

    raise SchemaValidationError(
        f"Unrecognized input format: '{name}'. "
        "Supported: .csv, .out, .npy, .npz, or builtin dataset name.",
        context={"input": name},
    )
