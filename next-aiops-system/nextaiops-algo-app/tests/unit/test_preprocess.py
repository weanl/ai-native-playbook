"""Unit tests for pipeline/preprocess.py."""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from nextaiops_algo.core.exceptions import SchemaValidationError
from nextaiops_algo.core.table import FieldRole, Table, TableSchema
from nextaiops_algo.pipeline.preprocess import read_csv_to_table, split_by_time


class TestReadCsvToTable:
    """Tests for read_csv_to_table function."""

    def test_basic_csv_with_timestamp_metric_label(self) -> None:
        """Test CSV with timestamp, value, is_anomaly columns."""
        csv_content = "timestamp,value,is_anomaly\n1,10.0,0\n2,15.0,1\n3,20.0,0"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            path = Path(f.name)

        table = read_csv_to_table(path)

        assert table.schema.roles["timestamp"] == FieldRole.TIMESTAMP
        assert table.schema.roles["value"] == FieldRole.METRIC
        assert table.schema.roles["is_anomaly"] == FieldRole.LABEL
        assert len(table.df) == 3
        path.unlink()

    def test_csv_without_timestamp(self) -> None:
        """Test CSV without timestamp column."""
        csv_content = "value,label\n10.0,0\n15.0,1"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            path = Path(f.name)

        table = read_csv_to_table(path)

        assert table.schema.roles["value"] == FieldRole.METRIC
        assert table.schema.roles["label"] == FieldRole.LABEL
        assert table.timestamps() is None
        path.unlink()

    def test_csv_without_label(self) -> None:
        """Test CSV without label column."""
        csv_content = "timestamp,value\n1,10.0\n2,15.0"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            path = Path(f.name)

        table = read_csv_to_table(path)

        assert table.schema.roles["timestamp"] == FieldRole.TIMESTAMP
        assert table.schema.roles["value"] == FieldRole.METRIC
        assert table.labels() is None
        path.unlink()

    def test_multi_metric_csv(self) -> None:
        """Test CSV with multiple metric columns."""
        csv_content = "timestamp,value1,value2,label\n1,10.0,20.0,0\n2,15.0,25.0,1"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            path = Path(f.name)

        table = read_csv_to_table(path)

        assert table.schema.roles["value1"] == FieldRole.METRIC
        assert table.schema.roles["value2"] == FieldRole.METRIC
        assert len(table.metrics().columns) == 2
        path.unlink()

    def test_skips_non_numeric_columns(self) -> None:
        """Test that non-numeric columns are skipped with warning."""
        csv_content = "timestamp,value,name\n1,10.0,alice\n2,15.0,bob"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            path = Path(f.name)

        table = read_csv_to_table(path)

        assert "value" in table.schema.roles
        assert "name" not in table.schema.roles
        path.unlink()

    def test_column_name_case_insensitive(self) -> None:
        """Test that column name matching is case-insensitive."""
        csv_content = "TIMEStamp,VALUE,IS_ANOMALY\n1,10.0,0\n2,15.0,1"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            path = Path(f.name)

        table = read_csv_to_table(path)

        assert table.schema.roles["TIMEStamp"] == FieldRole.TIMESTAMP
        assert table.schema.roles["VALUE"] == FieldRole.METRIC
        assert table.schema.roles["IS_ANOMALY"] == FieldRole.LABEL
        path.unlink()

    def test_raises_on_no_metric(self) -> None:
        """Test that SchemaValidationError is raised when no METRIC columns."""
        csv_content = "name,description\nalice,good\nbob,bad"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            path = Path(f.name)

        with pytest.raises(SchemaValidationError, match="No METRIC columns"):
            read_csv_to_table(path)
        path.unlink()

    def test_raises_on_multiple_timestamps(self) -> None:
        """Test that SchemaValidationError is raised on multiple TIMESTAMP matches."""
        csv_content = "timestamp,time,value\n1,1,10.0\n2,2,15.0"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            path = Path(f.name)

        with pytest.raises(SchemaValidationError, match="2 TIMESTAMP columns"):
            read_csv_to_table(path)
        path.unlink()

    def test_raises_on_multiple_labels(self) -> None:
        """Test that SchemaValidationError is raised on multiple LABEL matches."""
        csv_content = "value,label,anomaly\n10.0,0,0\n15.0,1,1"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            path = Path(f.name)

        with pytest.raises(SchemaValidationError, match="2 LABEL columns"):
            read_csv_to_table(path)
        path.unlink()

    def test_raises_on_file_not_found(self) -> None:
        """Test that FileNotFoundError is raised for missing file."""
        with pytest.raises(FileNotFoundError):
            read_csv_to_table(Path("/nonexistent/file.csv"))


class TestSplitByTime:
    """Tests for split_by_time function."""

    def _make_table(self, n_rows: int) -> Table:
        """Helper to create a simple Table for testing."""
        df = pd.DataFrame({
            "timestamp": range(n_rows),
            "value": [float(i) for i in range(n_rows)],
            "label": [0] * n_rows,
        })
        schema = TableSchema(roles={
            "timestamp": FieldRole.TIMESTAMP,
            "value": FieldRole.METRIC,
            "label": FieldRole.LABEL,
        })
        return Table(df=df, schema=schema)

    def test_default_split_ratio(self) -> None:
        """Test default 0.7 split ratio."""
        table = self._make_table(100)
        train, test = split_by_time(table)

        assert len(train.df) == 70
        assert len(test.df) == 30

    def test_custom_split_ratio(self) -> None:
        """Test custom split ratio."""
        table = self._make_table(100)
        train, test = split_by_time(table, ratio=0.8)

        assert len(train.df) == 80
        assert len(test.df) == 20

    def test_preserves_schema(self) -> None:
        """Test that split tables preserve original schema."""
        table = self._make_table(10)
        train, test = split_by_time(table)

        assert train.schema.roles == table.schema.roles
        assert test.schema.roles == table.schema.roles

    def test_time_order_preserved(self) -> None:
        """Test that split preserves time order (first part train, rest test)."""
        table = self._make_table(10)
        train, test = split_by_time(table, ratio=0.5)

        # Train should have timestamps 0-4
        assert list(train.df["timestamp"]) == [0, 1, 2, 3, 4]
        # Test should have timestamps 5-9
        assert list(test.df["timestamp"]) == [5, 6, 7, 8, 9]

    def test_raises_on_invalid_ratio_zero(self) -> None:
        """Test that ValueError is raised for ratio=0."""
        table = self._make_table(10)
        with pytest.raises(ValueError, match="between 0 and 1"):
            split_by_time(table, ratio=0.0)

    def test_raises_on_invalid_ratio_one(self) -> None:
        """Test that ValueError is raised for ratio=1."""
        table = self._make_table(10)
        with pytest.raises(ValueError, match="between 0 and 1"):
            split_by_time(table, ratio=1.0)

    def test_raises_on_invalid_ratio_negative(self) -> None:
        """Test that ValueError is raised for negative ratio."""
        table = self._make_table(10)
        with pytest.raises(ValueError, match="between 0 and 1"):
            split_by_time(table, ratio=-0.5)


