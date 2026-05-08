"""Unit tests for Three Sigma algorithm."""

import numpy as np
import pandas as pd
import pytest

from nextaiops_algo.algorithms.three_sigma import ThreeSigma
from nextaiops_algo.core.table import FieldRole, Table, TableSchema


class TestThreeSigma:
    """Tests for ThreeSigma algorithm."""

    def test_single_metric_output_columns(self) -> None:
        """Test single metric input produces required output columns."""
        # Create simple metric data
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=100),
            "value": np.random.randn(100) * 10 + 50,
        })

        schema = TableSchema(roles={
            "timestamp": FieldRole.TIMESTAMP,
            "value": FieldRole.METRIC,
        })
        table = Table(df=df, schema=schema)

        algo = ThreeSigma()
        algo.fit(table)
        result = algo.detect(table)

        # Check required columns exist
        assert "predicted_label" in result.df.columns
        assert "value" in result.df.columns
        assert "value.anomaly_score" in result.df.columns
        assert "value.threshold_upper" in result.df.columns
        assert "value.threshold_lower" in result.df.columns

        # Check roles
        assert result.schema.roles["predicted_label"] == FieldRole.LABEL
        assert result.schema.roles["value"] == FieldRole.METRIC
        assert result.schema.roles["value.anomaly_score"] == FieldRole.METRIC
        assert result.schema.roles["value.threshold_upper"] == FieldRole.METRIC
        assert result.schema.roles["value.threshold_lower"] == FieldRole.METRIC

    def test_multi_metric_output_columns(self) -> None:
        """Test multi metric input produces columns for each metric."""
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=100),
            "metric1": np.random.randn(100) * 10 + 50,
            "metric2": np.random.randn(100) * 5 + 100,
        })

        schema = TableSchema(roles={
            "timestamp": FieldRole.TIMESTAMP,
            "metric1": FieldRole.METRIC,
            "metric2": FieldRole.METRIC,
        })
        table = Table(df=df, schema=schema)

        algo = ThreeSigma()
        algo.fit(table)
        result = algo.detect(table)

        # Check columns for metric1
        assert "metric1" in result.df.columns
        assert "metric1.anomaly_score" in result.df.columns
        assert "metric1.threshold_upper" in result.df.columns
        assert "metric1.threshold_lower" in result.df.columns

        # Check columns for metric2
        assert "metric2" in result.df.columns
        assert "metric2.anomaly_score" in result.df.columns
        assert "metric2.threshold_upper" in result.df.columns
        assert "metric2.threshold_lower" in result.df.columns

        # Check predicted_label exists
        assert "predicted_label" in result.df.columns
        assert result.schema.roles["predicted_label"] == FieldRole.LABEL

    def test_output_row_count_matches_input(self) -> None:
        """Test output has same row count as input."""
        df = pd.DataFrame({
            "value": np.random.randn(50) * 10 + 50,
        })

        schema = TableSchema(roles={"value": FieldRole.METRIC})
        table = Table(df=df, schema=schema)

        algo = ThreeSigma()
        algo.fit(table)
        result = algo.detect(table)

        assert len(result.df) == len(table.df)

    def test_timestamp_copied_row_by_row(self) -> None:
        """Test timestamp is copied exactly when present."""
        timestamps = pd.date_range("2024-01-01", periods=100)
        df = pd.DataFrame({
            "timestamp": timestamps,
            "value": np.random.randn(100) * 10 + 50,
        })

        schema = TableSchema(roles={
            "timestamp": FieldRole.TIMESTAMP,
            "value": FieldRole.METRIC,
        })
        table = Table(df=df, schema=schema)

        algo = ThreeSigma()
        algo.fit(table)
        result = algo.detect(table)

        # Timestamp should be present and identical
        assert "timestamp" in result.df.columns
        assert result.df["timestamp"].equals(table.df["timestamp"])

    def test_no_timestamp_when_input_missing(self) -> None:
        """Test output has no timestamp when input lacks it."""
        df = pd.DataFrame({
            "value": np.random.randn(100) * 10 + 50,
        })

        schema = TableSchema(roles={"value": FieldRole.METRIC})
        table = Table(df=df, schema=schema)

        algo = ThreeSigma()
        algo.fit(table)
        result = algo.detect(table)

        assert "timestamp" not in result.df.columns

    def test_predicted_label_or_merge(self) -> None:
        """Test predicted_label is OR-merged across metrics."""
        # Construct data where only metric1 has an extreme outlier
        mean1, std1 = 50.0, 10.0
        mean2, std2 = 100.0, 5.0

        # metric1: one value > mean + 3*std
        values1 = np.random.randn(100) * std1 + mean1
        values1[50] = mean1 + 4 * std1  # clear outlier

        # metric2: all normal
        values2 = np.random.randn(100) * std2 + mean2

        df = pd.DataFrame({
            "metric1": values1,
            "metric2": values2,
        })

        schema = TableSchema(roles={
            "metric1": FieldRole.METRIC,
            "metric2": FieldRole.METRIC,
        })
        table = Table(df=df, schema=schema)

        algo = ThreeSigma()
        algo.fit(table)
        result = algo.detect(table)

        # Only row 50 should have predicted_label=1
        assert result.df["predicted_label"].iloc[50] == 1
        # Most other rows should be 0 (allowing for random outliers)
        assert result.df["predicted_label"].sum() >= 1

    def test_f1_greater_than_zero(self) -> None:
        """Test algorithm achieves F1 > 0 on simple labeled data."""
        # Generate data with known anomalies
        np.random.seed(42)

        normal_values = np.random.randn(90) * 10 + 50
        anomaly_values = np.random.randn(10) * 50 + 200  # extreme outliers

        values = np.concatenate([normal_values, anomaly_values])
        labels = np.array([0] * 90 + [1] * 10)

        df = pd.DataFrame({
            "value": values,
            "is_anomaly": labels,
        })

        schema = TableSchema(roles={
            "value": FieldRole.METRIC,
            "is_anomaly": FieldRole.LABEL,
        })
        table = Table(df=df, schema=schema)

        algo = ThreeSigma()
        algo.fit(table)
        result = algo.detect(table)

        # Compute F1 manually
        y_true = labels
        y_pred = result.df["predicted_label"].values

        tp = int(np.sum((y_true == 1) & (y_pred == 1)))
        fp = int(np.sum((y_true == 0) & (y_pred == 1)))
        fn = int(np.sum((y_true == 1) & (y_pred == 0)))

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        assert f1 > 0, "Algorithm should detect at least one anomaly"

    def test_registry_contains_three_sigma(self) -> None:
        """Test ThreeSigma is registered in REGISTRY."""
        from nextaiops_algo.algorithms.registry import REGISTRY

        # Import triggers registration via @register decorator
        assert "three_sigma" in REGISTRY