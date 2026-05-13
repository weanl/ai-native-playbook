"""Tests for TSBUADAdapter - verifying adapter mechanics with mock TSB-UAD models."""


import numpy as np
import pandas as pd
import pytest

from nextaiops_algo.algorithms.adapters.tsbuad_adapter import (
    TSBUADAdapter,
    _align_scores,
    _apply_threshold,
    _find_window_length,
    _sliding_window_convert,
)
from nextaiops_algo.algorithms.adapters.tsbuad_configs import TSBUADAlgoConfig
from nextaiops_algo.core.algorithm import TaskType
from nextaiops_algo.core.table import FieldRole, Table, TableSchema


def _make_single_metric_table(n: int = 100) -> Table:
    """Create a Table with a single METRIC column (value)."""
    values = np.random.randn(n).cumsum()  # random walk for realism
    df = pd.DataFrame({"value": values})
    roles = {"value": FieldRole.METRIC}
    return Table(df=df, schema=TableSchema(roles=roles))


def _make_multi_metric_table(n: int = 100) -> Table:
    """Create a Table with two METRIC columns."""
    df = pd.DataFrame(
        {
            "metric_0": np.random.randn(n).cumsum(),
            "metric_1": np.random.randn(n).cumsum(),
        }
    )
    roles = {"metric_0": FieldRole.METRIC, "metric_1": FieldRole.METRIC}
    return Table(df=df, schema=TableSchema(roles=roles))


def _make_table_with_timestamp(n: int = 100) -> Table:
    """Create a Table with timestamp + single METRIC."""
    timestamps = pd.date_range("2024-01-01", periods=n, freq="h")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "value": np.random.randn(n).cumsum(),
        }
    )
    roles = {"timestamp": FieldRole.TIMESTAMP, "value": FieldRole.METRIC}
    return Table(df=df, schema=TableSchema(roles=roles))


class MockTSBUADModel:
    """Mock TSB-UAD model that returns fixed decision_scores_ after fit."""

    def __init__(self, **kwargs: object) -> None:
        self.decision_scores_: np.ndarray | None = None
        self._kwargs = kwargs
        # Mock sklearn detector for scoring_method tests
        self.detector_ = MockSklearnDetector()

    def fit(self, X: np.ndarray) -> None:
        # Return random scores of length matching X
        n = len(X)
        self.decision_scores_ = np.random.rand(n).astype(float)


class MockSklearnDetector:
    """Mock sklearn detector with decision_function for test scoring."""

    def decision_function(self, X: np.ndarray) -> np.ndarray:
        """Return mock anomaly scores (negated for consistency)."""
        return np.random.rand(len(X)).astype(float)


MOCK_CONFIG = TSBUADAlgoConfig(
    name="mock_tsbuad",
    algo_class_path="tests.unit.test_tsbuad_adapter.MockTSBUADModel",
    default_params={},
    threshold_method="sigma",
    threshold_params={"n_sigma": 3},
    scoring_method="detector_decision_function",
)


class TestAlignScores:
    """Tests for score alignment from window-level to point-level."""

    def test_align_basic(self) -> None:
        """Scores aligned to original length with center-of-window strategy."""
        scores = np.array([1.0, 2.0, 3.0, 4.0])
        original_length = 7
        window = 4
        result = _align_scores(scores, original_length, window)
        assert len(result) == original_length
        # Center alignment: center_offset = 4//2 = 2
        # score[0] placed at pos 0+2=2, score[1] at 1+2=3, etc.
        # First 2 positions padded with score[0] (1.0)
        assert result[0] == 1.0  # padded with first score
        assert result[1] == 1.0  # padded with first score
        # Center positions: score[0] at pos 2, score[1] at pos 3
        assert result[2] == 1.0  # score[0] at center pos
        assert result[3] == 2.0  # score[1] at center pos
        # Remaining: score[2] at pos 4, score[3] at pos 5, then pad with last
        assert result[4] == 3.0  # score[2] at center pos
        assert result[5] == 4.0  # score[3] at center pos
        assert result[6] == 4.0  # trailing pad with last score

    def test_align_window_equals_length(self) -> None:
        """When window == 1, scores directly map to points."""
        scores = np.array([5.0, 6.0, 7.0])
        result = _align_scores(scores, 3, 1)
        np.testing.assert_array_equal(result, scores)

    def test_align_empty_scores(self) -> None:
        """Empty scores produce zeros."""
        result = _align_scores(np.array([]), 5, 3)
        assert len(result) == 5
        assert np.all(result == 0.0)


class TestApplyThreshold:
    """Tests for threshold strategies."""

    def test_sigma_threshold(self) -> None:
        """Sigma threshold: mean + n_sigma * std."""
        scores = np.array([1.0, 1.0, 1.0, 10.0])
        upper, lower, labels = _apply_threshold(scores, method="sigma", n_sigma=3.0)
        # np.mean([1,1,1,10]) = 3.25, np.std([1,1,1,10]) uses ddof=0 → 4.5/sqrt(4) = ~3.9686
        expected_mean = float(np.mean(scores))
        expected_std = float(np.std(scores))
        expected_upper = expected_mean + 3.0 * expected_std
        assert abs(upper - expected_upper) < 0.01
        assert lower == 0.0
        # 10.0 > threshold (3.25 + 3*3.97 ≈ 15.16), so NOT anomaly
        # Only checking that threshold formula is correct

    def test_percentile_threshold(self) -> None:
        """Percentile threshold marks top 2% as anomaly."""
        scores = np.arange(100, dtype=float)
        upper, lower, labels = _apply_threshold(scores, method="percentile", percentile=98.0)
        # np.percentile with 100 elements uses interpolation: result ≈ 97.02
        expected_upper = float(np.percentile(scores, 98))
        assert abs(upper - expected_upper) < 0.01
        # Values above threshold are anomalies
        assert labels[99] == 1

    def test_fixed_threshold(self) -> None:
        """Fixed threshold at specified value."""
        scores = np.array([0.5, 1.5, 2.5])
        upper, lower, labels = _apply_threshold(scores, method="fixed", fixed_value=1.0)
        assert upper == 1.0
        assert labels[1] == 1  # 1.5 > 1.0
        assert labels[2] == 1  # 2.5 > 1.0

    def test_invalid_method_raises(self) -> None:
        """Unknown threshold method raises ValueError."""
        with pytest.raises(ValueError, match="Unknown threshold method"):
            _apply_threshold(np.array([1.0]), method="bogus")

    def test_fixed_without_value_raises(self) -> None:
        """Fixed method without fixed_value raises ValueError."""
        with pytest.raises(ValueError, match="fixed_value must be provided"):
            _apply_threshold(np.array([1.0]), method="fixed")


class TestSlidingWindowConvert:
    """Tests for sliding window conversion utility."""

    def test_manual_sliding_window(self) -> None:
        """Manual sliding window produces correct shape."""
        series = np.arange(10, dtype=float)
        window = 3
        result = _sliding_window_convert(series, window)
        assert result.shape == (8, 3)  # 10 - 3 + 1 = 8
        np.testing.assert_array_equal(result[0], [0.0, 1.0, 2.0])

    def test_window_equals_length(self) -> None:
        """Window equal to series length produces single row."""
        series = np.arange(5, dtype=float)
        result = _sliding_window_convert(series, 5)
        assert result.shape == (1, 5)


class TestFindWindowLength:
    """Tests for window length determination."""

    def test_returns_positive_integer(self) -> None:
        """Window length is always >= 2."""
        series = np.random.randn(100)
        window = _find_window_length(series)
        assert isinstance(window, int)
        assert window >= 2

    def test_short_series_minimum_window(self) -> None:
        """Very short series still gets window >= 2."""
        series = np.array([1.0, 2.0, 3.0])
        window = _find_window_length(series)
        assert window >= 2


class TestTSBUADAdapterWithMock:
    """Tests for TSBUADAdapter using mock TSB-UAD model."""

    def test_adapter_name_from_config(self) -> None:
        """Adapter name matches config name."""
        adapter = TSBUADAdapter(config=MOCK_CONFIG)
        assert adapter.name == "mock_tsbuad"

    def test_adapter_protocol_attributes(self) -> None:
        """Adapter satisfies Algorithm protocol attributes."""
        adapter = TSBUADAdapter(config=MOCK_CONFIG)
        assert adapter.task_type == TaskType.ANOMALY_DETECTION
        assert adapter.required_input_roles == {FieldRole.METRIC}

    def test_fit_single_metric(self) -> None:
        """Fit with single metric creates one model."""
        adapter = TSBUADAdapter(config=MOCK_CONFIG)
        table = _make_single_metric_table(50)
        adapter.fit(table)
        assert "value" in adapter._metric_models
        assert "value" in adapter._metric_windows

    def test_fit_multi_metric(self) -> None:
        """Fit with multi-metric creates models for each column."""
        adapter = TSBUADAdapter(config=MOCK_CONFIG)
        table = _make_multi_metric_table(50)
        adapter.fit(table)
        assert "metric_0" in adapter._metric_models
        assert "metric_1" in adapter._metric_models

    def test_detect_output_contract_single_metric(self) -> None:
        """Detect output follows AnomalyDetector contract for single metric."""
        adapter = TSBUADAdapter(config=MOCK_CONFIG)
        table = _make_single_metric_table(50)
        adapter.fit(table)
        result = adapter.detect(table)

        # Required columns
        assert "predicted_label" in result.df.columns
        assert result.schema.roles["predicted_label"] == FieldRole.LABEL
        assert "value" in result.df.columns
        assert result.schema.roles["value"] == FieldRole.METRIC
        assert "value.anomaly_score" in result.df.columns
        assert "value.threshold_upper" in result.df.columns
        assert "value.threshold_lower" in result.df.columns

        # Row count alignment
        assert len(result.df) == len(table.df)

        # predicted_label is binary
        assert set(result.df["predicted_label"].unique()).issubset({0, 1})

    def test_detect_output_contract_multi_metric(self) -> None:
        """Detect output follows contract for multi-metric with OR merge."""
        adapter = TSBUADAdapter(config=MOCK_CONFIG)
        table = _make_multi_metric_table(50)
        adapter.fit(table)
        result = adapter.detect(table)

        # Both metrics have score/threshold columns
        for metric in ["metric_0", "metric_1"]:
            assert f"{metric}.anomaly_score" in result.df.columns
            assert f"{metric}.threshold_upper" in result.df.columns
            assert f"{metric}.threshold_lower" in result.df.columns

        assert len(result.df) == len(table.df)

    def test_detect_preserves_timestamp(self) -> None:
        """Detect output preserves timestamp column from input."""
        adapter = TSBUADAdapter(config=MOCK_CONFIG)
        table = _make_table_with_timestamp(50)
        adapter.fit(table)
        result = adapter.detect(table)

        assert "timestamp" in result.df.columns
        assert result.schema.roles["timestamp"] == FieldRole.TIMESTAMP

        # Timestamp values must match input
        input_ts = table.timestamps().reset_index(drop=True)
        output_ts = result.timestamps().reset_index(drop=True)
        assert input_ts.equals(output_ts)

    def test_detect_no_timestamp_input_no_timestamp_output(self) -> None:
        """Input without timestamp produces output without timestamp."""
        adapter = TSBUADAdapter(config=MOCK_CONFIG)
        table = _make_single_metric_table(50)
        adapter.fit(table)
        result = adapter.detect(table)

        assert result.timestamps() is None

    def test_detect_row_count_alignment(self) -> None:
        """Output row count equals input row count."""
        adapter = TSBUADAdapter(config=MOCK_CONFIG)
        for n in [20, 50, 100]:
            table = _make_single_metric_table(n)
            adapter.fit(table)
            result = adapter.detect(table)
            assert len(result.df) == n

    def test_percentile_threshold_config(self) -> None:
        """Adapter with percentile threshold config works."""
        config = TSBUADAlgoConfig(
            name="mock_pct",
            algo_class_path="tests.unit.test_tsbuad_adapter.MockTSBUADModel",
            default_params={},
            threshold_method="percentile",
            threshold_params={"percentile": 95},
        )
        adapter = TSBUADAdapter(config=config)
        table = _make_single_metric_table(50)
        adapter.fit(table)
        result = adapter.detect(table)
        assert "predicted_label" in result.df.columns
