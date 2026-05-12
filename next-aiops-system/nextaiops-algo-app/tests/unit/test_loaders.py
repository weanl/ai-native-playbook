"""Unit tests for datasets/loaders.py — CSV, .out, npy, npz, and unified entry."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nextaiops_algo.core.exceptions import SchemaValidationError
from nextaiops_algo.core.table import FieldRole
from nextaiops_algo.datasets.loaders import (
    read_csv_to_table,
    read_npy_to_table,
    read_npz_to_table,
    read_to_table,
    read_tsbuad_out_to_table,
)


def _write_csv(
    tmp_path: Path,
    filename: str = "test.csv",
    columns: dict[str, list] | None = None,
) -> Path:
    """Helper to write a CSV test file."""
    if columns is None:
        columns = {
            "timestamp": pd.date_range("2024-01-01", periods=10, freq="h").astype(str).tolist(),
            "value": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 100.0],
            "is_anomaly": [0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
        }
    df = pd.DataFrame(columns)
    path = tmp_path / filename
    df.to_csv(path, index=False)
    return path


def _write_out(
    tmp_path: Path,
    filename: str = "test.out",
    values: list[float] | None = None,
    labels: list[int] | None = None,
) -> Path:
    """Helper to write a .out test file."""
    if values is None:
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 100.0]
    if labels is None:
        labels = [0, 0, 0, 0, 0, 1]
    path = tmp_path / filename
    with open(path, "w") as f:
        for val, lbl in zip(values, labels, strict=True):
            f.write(f"{val} {lbl}\n")
    return path


def _write_npy(
    tmp_path: Path,
    data: np.ndarray | None = None,
    labels: np.ndarray | None = None,
) -> tuple[Path, Path | None]:
    """Helper to write .npy test files."""
    if data is None:
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 100.0])
    data_path = tmp_path / "data.npy"
    np.save(data_path, data)
    label_path = None
    if labels is not None:
        label_path = tmp_path / "label.npy"
        np.save(label_path, labels)
    return data_path, label_path


def _write_npz(
    tmp_path: Path,
    filename: str = "test.npz",
    data: np.ndarray | None = None,
    label: np.ndarray | None = None,
    timestamp: np.ndarray | None = None,
) -> Path:
    """Helper to write a .npz test file."""
    if data is None:
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 100.0])
    arrays = {"data": data}
    if label is not None:
        arrays["label"] = label
    if timestamp is not None:
        arrays["timestamp"] = timestamp
    path = tmp_path / filename
    np.savez(path, **arrays)
    return path


class TestReadCSVToTable:
    """Tests for read_csv_to_table."""

    def test_csv_with_timestamp_and_label(self, tmp_path: Path) -> None:
        """CSV with timestamp + metric + label loads correctly."""
        path = _write_csv(tmp_path)
        table = read_csv_to_table(path)

        assert "timestamp" in table.schema.roles
        assert table.schema.roles["timestamp"] == FieldRole.TIMESTAMP
        assert "value" in table.schema.roles
        assert table.schema.roles["value"] == FieldRole.METRIC
        assert "is_anomaly" in table.schema.roles
        assert table.schema.roles["is_anomaly"] == FieldRole.LABEL
        assert len(table.df) == 10

    def test_csv_without_timestamp(self, tmp_path: Path) -> None:
        """CSV without timestamp — only metric and label."""
        columns = {
            "value": [1.0, 2.0, 3.0],
            "label": [0, 0, 1],
        }
        path = _write_csv(tmp_path, columns=columns)
        table = read_csv_to_table(path)

        assert FieldRole.TIMESTAMP not in set(table.schema.roles.values())
        assert "value" in table.schema.roles
        assert table.schema.roles["value"] == FieldRole.METRIC

    def test_csv_without_label(self, tmp_path: Path) -> None:
        """CSV without label — only metric and timestamp."""
        columns = {
            "timestamp": pd.date_range("2024-01-01", periods=5, freq="h").astype(str).tolist(),
            "value": [1.0, 2.0, 3.0, 4.0, 5.0],
        }
        path = _write_csv(tmp_path, columns=columns)
        table = read_csv_to_table(path)

        assert FieldRole.LABEL not in set(table.schema.roles.values())
        assert "value" in table.schema.roles

    def test_csv_multi_metric(self, tmp_path: Path) -> None:
        """CSV with multiple METRIC columns."""
        columns = {
            "cpu": [10.0, 20.0, 30.0],
            "mem": [1.0, 2.0, 3.0],
        }
        path = _write_csv(tmp_path, columns=columns)
        table = read_csv_to_table(path)

        assert "cpu" in table.schema.roles
        assert "mem" in table.schema.roles
        assert table.schema.roles["cpu"] == FieldRole.METRIC
        assert table.schema.roles["mem"] == FieldRole.METRIC

    def test_csv_no_metric_raises_error(self, tmp_path: Path) -> None:
        """CSV with no numeric columns raises SchemaValidationError."""
        columns = {"name": ["a", "b", "c"]}
        path = _write_csv(tmp_path, columns=columns)
        with pytest.raises(SchemaValidationError, match="No METRIC"):
            read_csv_to_table(path)

    def test_csv_not_found_raises_error(self, tmp_path: Path) -> None:
        """Non-existent CSV file raises FileNotFoundError."""
        path = tmp_path / "nonexistent.csv"
        with pytest.raises(FileNotFoundError):
            read_csv_to_table(path)

    def test_csv_empty_raises_error(self, tmp_path: Path) -> None:
        """Empty CSV file raises SchemaValidationError."""
        path = tmp_path / "empty.csv"
        Path(path).write_text("value,is_anomaly\n")
        with pytest.raises(SchemaValidationError, match="empty"):
            read_csv_to_table(path)


class TestReadTSBUADOutToTable:
    """Tests for read_tsbuad_out_to_table."""

    def test_out_file_loads_correctly(self, tmp_path: Path) -> None:
        """TSB-UAD .out file loads with value as METRIC, is_anomaly as LABEL."""
        path = _write_out(tmp_path)
        table = read_tsbuad_out_to_table(path)

        assert "value" in table.schema.roles
        assert table.schema.roles["value"] == FieldRole.METRIC
        assert "is_anomaly" in table.schema.roles
        assert table.schema.roles["is_anomaly"] == FieldRole.LABEL
        assert len(table.df) == 6

    def test_out_file_no_timestamp(self, tmp_path: Path) -> None:
        """TSB-UAD .out file has no TIMESTAMP role."""
        path = _write_out(tmp_path)
        table = read_tsbuad_out_to_table(path)

        assert FieldRole.TIMESTAMP not in set(table.schema.roles.values())

    def test_out_wrong_column_count_raises(self, tmp_path: Path) -> None:
        """TSB-UAD .out with 3 columns raises SchemaValidationError."""
        path = tmp_path / "bad.out"
        with open(path, "w") as f:
            f.write("1.0 0 5.0\n")
            f.write("2.0 1 3.0\n")
        with pytest.raises(SchemaValidationError, match="2 columns"):
            read_tsbuad_out_to_table(path)

    def test_out_not_found_raises(self, tmp_path: Path) -> None:
        """Non-existent .out file raises FileNotFoundError."""
        path = tmp_path / "nonexistent.out"
        with pytest.raises(FileNotFoundError):
            read_tsbuad_out_to_table(path)

    def test_out_empty_raises(self, tmp_path: Path) -> None:
        """Empty .out file raises SchemaValidationError."""
        path = tmp_path / "empty.out"
        Path(path).write_text("")
        with pytest.raises(SchemaValidationError, match="empty"):
            read_tsbuad_out_to_table(path)


class TestReadNpyToTable:
    """Tests for read_npy_to_table."""

    def test_1d_npy_single_metric(self, tmp_path: Path) -> None:
        """1D .npy → single metric_0 column."""
        data_path, _ = _write_npy(tmp_path)
        table = read_npy_to_table(data_path)

        assert "metric_0" in table.schema.roles
        assert table.schema.roles["metric_0"] == FieldRole.METRIC
        assert len(table.df) == 6

    def test_2d_npy_multi_metric(self, tmp_path: Path) -> None:
        """2D .npy → metric_0, metric_1 columns."""
        data = np.column_stack([np.arange(5.0), np.arange(5.0) + 10])
        data_path, _ = _write_npy(tmp_path, data=data)
        table = read_npy_to_table(data_path)

        assert "metric_0" in table.schema.roles
        assert "metric_1" in table.schema.roles

    def test_npy_with_labels(self, tmp_path: Path) -> None:
        """npy + label → is_anomaly LABEL column."""
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        labels = np.array([0, 0, 1, 0, 0])
        data_path, label_path = _write_npy(tmp_path, data=data, labels=labels)
        table = read_npy_to_table(data_path, label_path)

        assert "is_anomaly" in table.schema.roles
        assert table.schema.roles["is_anomaly"] == FieldRole.LABEL

    def test_npy_label_length_mismatch_raises(self, tmp_path: Path) -> None:
        """npy + mismatched label length raises SchemaValidationError."""
        data = np.array([1.0, 2.0, 3.0])
        labels = np.array([0, 1])  # Only 2 labels for 3 data points
        data_path, label_path = _write_npy(tmp_path, data=data, labels=labels)
        with pytest.raises(SchemaValidationError, match="Label length"):
            read_npy_to_table(data_path, label_path)

    def test_npy_no_timestamp(self, tmp_path: Path) -> None:
        """npy format has no TIMESTAMP role."""
        data_path, _ = _write_npy(tmp_path)
        table = read_npy_to_table(data_path)
        assert FieldRole.TIMESTAMP not in set(table.schema.roles.values())

    def test_npy_not_found_raises(self, tmp_path: Path) -> None:
        """Non-existent .npy file raises FileNotFoundError."""
        path = tmp_path / "nonexistent.npy"
        with pytest.raises(FileNotFoundError):
            read_npy_to_table(path)

    def test_npy_3d_raises_error(self, tmp_path: Path) -> None:
        """3D .npy raises SchemaValidationError."""
        data = np.ones((5, 3, 2))
        data_path, _ = _write_npy(tmp_path, data=data)
        with pytest.raises(SchemaValidationError, match="1D or 2D"):
            read_npy_to_table(data_path)


class TestReadNpzToTable:
    """Tests for read_npz_to_table."""

    def test_npz_with_data_only(self, tmp_path: Path) -> None:
        """npz with data only → single metric."""
        path = _write_npz(tmp_path)
        table = read_npz_to_table(path)

        assert "metric_0" in table.schema.roles

    def test_npz_with_data_and_label(self, tmp_path: Path) -> None:
        """npz with data + label → metric + is_anomaly."""
        data = np.array([1.0, 2.0, 3.0])
        label = np.array([0, 0, 1])
        path = _write_npz(tmp_path, data=data, label=label)
        table = read_npz_to_table(path)

        assert "is_anomaly" in table.schema.roles
        assert table.schema.roles["is_anomaly"] == FieldRole.LABEL

    def test_npz_with_timestamp(self, tmp_path: Path) -> None:
        """npz with data + timestamp → metric + TIMESTAMP."""
        data = np.array([1.0, 2.0, 3.0])
        timestamp = np.array(["2024-01-01", "2024-01-02", "2024-01-03"])
        path = _write_npz(tmp_path, data=data, timestamp=timestamp)
        table = read_npz_to_table(path)

        assert "timestamp" in table.schema.roles
        assert table.schema.roles["timestamp"] == FieldRole.TIMESTAMP

    def test_npz_no_data_key_raises(self, tmp_path: Path) -> None:
        """npz without 'data' key raises SchemaValidationError."""
        path = tmp_path / "bad.npz"
        np.savez(path, values=np.array([1.0, 2.0]))
        with pytest.raises(SchemaValidationError, match="'data' key"):
            read_npz_to_table(path)

    def test_npz_label_length_mismatch_raises(self, tmp_path: Path) -> None:
        """npz with mismatched label length raises SchemaValidationError."""
        data = np.array([1.0, 2.0, 3.0])
        label = np.array([0, 1])  # Mismatch
        path = _write_npz(tmp_path, data=data, label=label)
        with pytest.raises(SchemaValidationError, match="Label length"):
            read_npz_to_table(path)

    def test_npz_timestamp_length_mismatch_raises(self, tmp_path: Path) -> None:
        """npz with mismatched timestamp length raises SchemaValidationError."""
        data = np.array([1.0, 2.0, 3.0])
        timestamp = np.array(["2024-01-01", "2024-01-02"])  # Mismatch
        path = _write_npz(tmp_path, data=data, timestamp=timestamp)
        with pytest.raises(SchemaValidationError, match="Timestamp length"):
            read_npz_to_table(path)

    def test_npz_not_found_raises(self, tmp_path: Path) -> None:
        """Non-existent .npz file raises FileNotFoundError."""
        path = tmp_path / "nonexistent.npz"
        with pytest.raises(FileNotFoundError):
            read_npz_to_table(path)


class TestReadToTable:
    """Tests for unified entry read_to_table."""

    def test_csv_dispatch(self, tmp_path: Path) -> None:
        """read_to_table dispatches to CSV loader for .csv suffix."""
        path = _write_csv(tmp_path)
        table = read_to_table(path)
        assert "value" in table.schema.roles

    def test_out_dispatch(self, tmp_path: Path) -> None:
        """read_to_table dispatches to .out loader for .out suffix."""
        path = _write_out(tmp_path)
        table = read_to_table(path)
        assert "value" in table.schema.roles

    def test_npy_dispatch(self, tmp_path: Path) -> None:
        """read_to_table dispatches to npy loader for .npy suffix."""
        data = np.array([1.0, 2.0, 3.0])
        data_path, _ = _write_npy(tmp_path, data=data)
        table = read_to_table(data_path)
        assert "metric_0" in table.schema.roles

    def test_npz_dispatch(self, tmp_path: Path) -> None:
        """read_to_table dispatches to npz loader for .npz suffix."""
        path = _write_npz(tmp_path)
        table = read_to_table(path)
        assert "metric_0" in table.schema.roles

    def test_builtin_dispatch(self) -> None:
        """read_to_table dispatches to builtin for known dataset name."""
        table = read_to_table("yahoo_sample")
        assert "value" in table.schema.roles

    def test_unknown_format_raises(self) -> None:
        """read_to_table raises SchemaValidationError for unknown format."""
        with pytest.raises(SchemaValidationError, match="Unrecognized"):
            read_to_table("something.xyz")

    def test_unknown_builtin_name_dispatches_to_path(self, tmp_path: Path) -> None:
        """Unknown name without suffix raises SchemaValidationError."""
        with pytest.raises(SchemaValidationError, match="Unrecognized"):
            read_to_table("unknown_dataset")
