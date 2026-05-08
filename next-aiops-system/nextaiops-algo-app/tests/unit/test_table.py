"""Unit tests for Table."""

import pandas as pd
import pytest

from nextaiops_algo.core import FieldRole, SchemaValidationError, Table, TableSchema


class TestTableConstruction:
    """Tests for Table construction and validation."""

    def test_single_metric_table_construction(self) -> None:
        """Table with single METRIC column constructs correctly."""
        df = pd.DataFrame({"value": [1.0, 2.0, 3.0]})
        schema = TableSchema(roles={"value": FieldRole.METRIC})
        table = Table(df=df, schema=schema)
        assert len(table.df) == 3
        assert table.metrics().columns.tolist() == ["value"]

    def test_multi_metric_table_construction(self) -> None:
        """Table with multiple METRIC columns constructs correctly."""
        df = pd.DataFrame({"value1": [1.0, 2.0], "value2": [3.0, 4.0]})
        schema = TableSchema(roles={"value1": FieldRole.METRIC, "value2": FieldRole.METRIC})
        table = Table(df=df, schema=schema)
        metrics = table.metrics()
        assert metrics.columns.tolist() == ["value1", "value2"]
        assert len(metrics) == 2

    def test_table_with_timestamp(self) -> None:
        """Table with TIMESTAMP column constructs correctly."""
        df = pd.DataFrame({"ts": [0, 1, 2], "value": [1.0, 2.0, 3.0]})
        schema = TableSchema(roles={"ts": FieldRole.TIMESTAMP, "value": FieldRole.METRIC})
        table = Table(df=df, schema=schema)
        timestamps = table.timestamps()
        assert timestamps is not None
        assert timestamps.tolist() == [0, 1, 2]

    def test_table_with_label(self) -> None:
        """Table with LABEL column constructs correctly."""
        df = pd.DataFrame({"value": [1.0, 2.0], "label": [0, 1]})
        schema = TableSchema(roles={"value": FieldRole.METRIC, "label": FieldRole.LABEL})
        table = Table(df=df, schema=schema)
        labels = table.labels()
        assert labels is not None
        assert labels.tolist() == [0, 1]

    def test_table_without_timestamp(self) -> None:
        """Table without TIMESTAMP column returns None for timestamps()."""
        df = pd.DataFrame({"value": [1.0, 2.0]})
        schema = TableSchema(roles={"value": FieldRole.METRIC})
        table = Table(df=df, schema=schema)
        assert table.timestamps() is None

    def test_table_without_label(self) -> None:
        """Table without LABEL column returns None for labels()."""
        df = pd.DataFrame({"value": [1.0, 2.0]})
        schema = TableSchema(roles={"value": FieldRole.METRIC})
        table = Table(df=df, schema=schema)
        assert table.labels() is None


class TestTableValidation:
    """Tests for Table schema validation errors."""

    def test_no_metric_raises_error(self) -> None:
        """Table with no METRIC column raises SchemaValidationError."""
        df = pd.DataFrame({"ts": [0, 1], "label": [0, 1]})
        schema = TableSchema(roles={"ts": FieldRole.TIMESTAMP, "label": FieldRole.LABEL})
        with pytest.raises(SchemaValidationError, match="at least 1 METRIC"):
            Table(df=df, schema=schema)

    def test_multiple_timestamp_raises_error(self) -> None:
        """Table with more than 1 TIMESTAMP column raises SchemaValidationError."""
        df = pd.DataFrame({"ts1": [0, 1], "ts2": [2, 3], "value": [1.0, 2.0]})
        schema = TableSchema(
            roles={"ts1": FieldRole.TIMESTAMP, "ts2": FieldRole.TIMESTAMP, "value": FieldRole.METRIC}
        )
        with pytest.raises(SchemaValidationError, match="at most 1 TIMESTAMP"):
            Table(df=df, schema=schema)

    def test_multiple_label_raises_error(self) -> None:
        """Table with more than 1 LABEL column raises SchemaValidationError."""
        df = pd.DataFrame({"value": [1.0, 2.0], "label1": [0, 1], "label2": [1, 0]})
        schema = TableSchema(
            roles={"value": FieldRole.METRIC, "label1": FieldRole.LABEL, "label2": FieldRole.LABEL}
        )
        with pytest.raises(SchemaValidationError, match="at most 1 LABEL"):
            Table(df=df, schema=schema)

    def test_missing_column_raises_error(self) -> None:
        """Table with roles referencing non-existent columns raises SchemaValidationError."""
        df = pd.DataFrame({"value": [1.0, 2.0]})
        schema = TableSchema(roles={"value": FieldRole.METRIC, "missing": FieldRole.LABEL})
        with pytest.raises(SchemaValidationError, match="not found in DataFrame"):
            Table(df=df, schema=schema)


class TestTableImmutability:
    """Tests for Table immutability - modifying returned data should not affect original."""

    def test_metrics_returns_copy(self) -> None:
        """Modifying metrics() result does not affect original Table."""
        df = pd.DataFrame({"value": [1.0, 2.0, 3.0]})
        schema = TableSchema(roles={"value": FieldRole.METRIC})
        table = Table(df=df, schema=schema)

        metrics = table.metrics()
        metrics["value"] = [10.0, 20.0, 30.0]

        # Original table should be unchanged
        assert table.df["value"].tolist() == [1.0, 2.0, 3.0]

    def test_timestamps_returns_copy(self) -> None:
        """Modifying timestamps() result does not affect original Table."""
        df = pd.DataFrame({"ts": [0, 1, 2], "value": [1.0, 2.0, 3.0]})
        schema = TableSchema(roles={"ts": FieldRole.TIMESTAMP, "value": FieldRole.METRIC})
        table = Table(df=df, schema=schema)

        timestamps = table.timestamps()
        assert timestamps is not None
        timestamps[0] = 100

        # Original table should be unchanged
        assert table.df["ts"].tolist() == [0, 1, 2]

    def test_labels_returns_copy(self) -> None:
        """Modifying labels() result does not affect original Table."""
        df = pd.DataFrame({"value": [1.0, 2.0], "label": [0, 1]})
        schema = TableSchema(roles={"value": FieldRole.METRIC, "label": FieldRole.LABEL})
        table = Table(df=df, schema=schema)

        labels = table.labels()
        assert labels is not None
        labels[0] = 1

        # Original table should be unchanged
        assert table.df["label"].tolist() == [0, 1]

    def test_modifying_original_df_does_not_affect_table(self) -> None:
        """Modifying the df passed to Table constructor does not affect Table."""
        df = pd.DataFrame({"value": [1.0, 2.0, 3.0]})
        schema = TableSchema(roles={"value": FieldRole.METRIC})
        table = Table(df=df, schema=schema)

        # Modify original df
        df["value"] = [10.0, 20.0, 30.0]

        # Table should have its own copy (pydantic validates the input)
        # Note: pydantic may or may not copy DataFrame; this test verifies behavior
        retrieved = table.metrics()
        # If pydantic doesn't copy, modifying df would affect table
        # We test that retrieved data matches what was passed at construction
        # pydantic BaseModel copies mutable data by default
        assert retrieved["value"].tolist() == [1.0, 2.0, 3.0]
