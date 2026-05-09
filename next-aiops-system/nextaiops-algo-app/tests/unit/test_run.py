"""Unit tests for pipeline/run.py validation functions."""

import pandas as pd
import pytest

from nextaiops_algo.core.algorithm import TaskType
from nextaiops_algo.core.exceptions import SchemaValidationError
from nextaiops_algo.core.table import FieldRole, Table, TableSchema
from nextaiops_algo.pipeline.run import _validate_input, _validate_output


class MockAlgorithm:
    """Mock algorithm for testing validation - requires only METRIC."""

    name = "mock_algo"
    task_type = TaskType.ANOMALY_DETECTION
    required_input_roles = {FieldRole.METRIC}


class MockAlgorithmWithTimestamp:
    """Mock algorithm that requires both METRIC and TIMESTAMP."""

    name = "mock_algo_ts"
    task_type = TaskType.ANOMALY_DETECTION
    required_input_roles = {FieldRole.METRIC, FieldRole.TIMESTAMP}


def _make_table(
    values: list[float],
    with_timestamp: bool = False,
    with_label: bool = False,
    predicted_label: list[int] | None = None,
) -> Table:
    """Helper to create a Table for testing."""
    df_data: dict[str, list] = {"value": values}

    if with_timestamp:
        df_data["timestamp"] = list(range(len(values)))

    if with_label:
        df_data["label"] = [0] * len(values)

    if predicted_label is not None:
        df_data["predicted_label"] = predicted_label

    df = pd.DataFrame(df_data)

    roles: dict[str, FieldRole] = {"value": FieldRole.METRIC}
    if with_timestamp:
        roles["timestamp"] = FieldRole.TIMESTAMP
    if with_label:
        roles["label"] = FieldRole.LABEL
    if predicted_label is not None:
        roles["predicted_label"] = FieldRole.LABEL

    schema = TableSchema(roles=roles)
    return Table(df=df, schema=schema)


class TestValidateInput:
    """Tests for _validate_input function."""

    def test_passes_with_required_roles(self) -> None:
        """Test that validation passes when required roles present."""
        table = _make_table([10.0, 15.0, 20.0])
        algo = MockAlgorithm()

        _validate_input(table, algo)  # Should not raise

    def test_raises_on_missing_required_role(self) -> None:
        """Test that SchemaValidationError raised when required role missing."""
        # Create table with METRIC but no TIMESTAMP
        table = _make_table([10.0, 15.0, 20.0])  # No timestamp

        algo = MockAlgorithmWithTimestamp()  # Requires both METRIC and TIMESTAMP

        with pytest.raises(SchemaValidationError, match="requires roles"):
            _validate_input(table, algo)

    def test_message_includes_algorithm_name(self) -> None:
        """Test that error message includes algorithm name."""
        table = _make_table([10.0, 15.0, 20.0])  # No timestamp

        algo = MockAlgorithmWithTimestamp()

        with pytest.raises(SchemaValidationError, match="mock_algo_ts"):
            _validate_input(table, algo)


class TestValidateOutput:
    """Tests for _validate_output function."""

    def test_passes_with_valid_output(self) -> None:
        """Test that validation passes with valid output."""
        input_table = _make_table([10.0, 15.0, 20.0], predicted_label=[0, 1, 0])
        output_table = _make_table([10.0, 15.0, 20.0], predicted_label=[0, 1, 0])
        algo = MockAlgorithm()

        _validate_output(input_table, output_table, algo)  # Should not raise

    def test_raises_on_missing_predicted_label(self) -> None:
        """Test that SchemaValidationError raised when predicted_label missing."""
        input_table = _make_table([10.0, 15.0, 20.0])
        output_table = _make_table([10.0, 15.0, 20.0])  # No predicted_label
        algo = MockAlgorithm()

        with pytest.raises(SchemaValidationError, match="missing.*predicted_label"):
            _validate_output(input_table, output_table, algo)

    def test_raises_on_predicted_label_wrong_role(self) -> None:
        """Test that error raised when predicted_label has wrong role."""
        input_table = _make_table([10.0, 15.0, 20.0])

        # Create output with predicted_label as METRIC (wrong role)
        df = pd.DataFrame({"value": [10.0, 15.0, 20.0], "predicted_label": [0, 1, 0]})
        schema = TableSchema(
            roles={"value": FieldRole.METRIC, "predicted_label": FieldRole.METRIC}
        )
        output_table = Table(df=df, schema=schema)

        algo = MockAlgorithm()

        with pytest.raises(SchemaValidationError, match="predicted_label.*role LABEL"):
            _validate_output(input_table, output_table, algo)

    def test_raises_on_row_count_mismatch(self) -> None:
        """Test that SchemaValidationError raised when row counts differ."""
        input_table = _make_table([10.0, 15.0, 20.0], predicted_label=[0, 1, 0])
        output_table = _make_table([10.0, 15.0], predicted_label=[0, 1])  # Only 2 rows
        algo = MockAlgorithm()

        with pytest.raises(SchemaValidationError, match="row count"):
            _validate_output(input_table, output_table, algo)

    def test_raises_on_timestamp_missing_in_output(self) -> None:
        """Test that error raised when input has timestamp but output doesn't."""
        input_table = _make_table(
            [10.0, 15.0, 20.0], with_timestamp=True, predicted_label=[0, 1, 0]
        )
        output_table = _make_table([10.0, 15.0, 20.0], predicted_label=[0, 1, 0])
        algo = MockAlgorithm()

        with pytest.raises(SchemaValidationError, match="timestamp.*output"):
            _validate_output(input_table, output_table, algo)

    def test_raises_on_timestamp_not_aligned(self) -> None:
        """Test that error raised when timestamp values don't match."""
        # Input with timestamps 0, 1, 2
        df_input = pd.DataFrame({
            "timestamp": [0, 1, 2],
            "value": [10.0, 15.0, 20.0],
            "predicted_label": [0, 1, 0],
        })
        schema_input = TableSchema(
            roles={
                "timestamp": FieldRole.TIMESTAMP,
                "value": FieldRole.METRIC,
                "predicted_label": FieldRole.LABEL,
            }
        )
        input_table = Table(df=df_input, schema=schema_input)

        # Output with timestamps 0, 1, 5 (mismatched)
        df_output = pd.DataFrame({
            "timestamp": [0, 1, 5],
            "value": [10.0, 15.0, 20.0],
            "predicted_label": [0, 1, 0],
        })
        schema_output = TableSchema(
            roles={
                "timestamp": FieldRole.TIMESTAMP,
                "value": FieldRole.METRIC,
                "predicted_label": FieldRole.LABEL,
            }
        )
        output_table = Table(df=df_output, schema=schema_output)

        algo = MockAlgorithm()

        with pytest.raises(SchemaValidationError, match="timestamp.*match"):
            _validate_output(input_table, output_table, algo)

    def test_passes_with_aligned_timestamps(self) -> None:
        """Test that validation passes when timestamps are aligned."""
        df = pd.DataFrame({
            "timestamp": [0, 1, 2],
            "value": [10.0, 15.0, 20.0],
            "predicted_label": [0, 1, 0],
        })
        schema = TableSchema(
            roles={
                "timestamp": FieldRole.TIMESTAMP,
                "value": FieldRole.METRIC,
                "predicted_label": FieldRole.LABEL,
            }
        )
        input_table = Table(df=df.copy(), schema=schema)
        output_table = Table(df=df.copy(), schema=schema)

        algo = MockAlgorithm()

        _validate_output(input_table, output_table, algo)  # Should not raise
