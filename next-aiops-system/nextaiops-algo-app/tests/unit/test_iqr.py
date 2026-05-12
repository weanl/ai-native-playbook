"""Unit tests for algorithms/iqr.py."""

import pandas as pd
import pytest

from nextaiops_algo.algorithms.iqr import IQR
from nextaiops_algo.algorithms.registry import REGISTRY
from nextaiops_algo.core.algorithm import TaskType
from nextaiops_algo.core.table import FieldRole, Table, TableSchema


def _make_table(
    values: list[float] | dict[str, list[float]],
    labels: list[int] | None = None,
    has_timestamp: bool = False,
) -> Table:
    """Helper to create input Table for testing."""
    if isinstance(values, dict):
        df = pd.DataFrame(values)
        roles: dict[str, FieldRole] = dict.fromkeys(values, FieldRole.METRIC)
    else:
        df = pd.DataFrame({"value": values})
        roles = {"value": FieldRole.METRIC}

    if labels is not None:
        df["label"] = labels
        roles["label"] = FieldRole.LABEL

    if has_timestamp:
        df["timestamp"] = pd.date_range("2024-01-01", periods=len(df), freq="h")
        roles["timestamp"] = FieldRole.TIMESTAMP

    schema = TableSchema(roles=roles)
    return Table(df=df, schema=schema)


class TestIQRRegistry:
    """Tests for IQR algorithm registration."""

    def test_registry_contains_iqr(self) -> None:
        """REGISTRY must contain 'iqr' after module import."""
        assert "iqr" in REGISTRY

    def test_registry_iqr_is_iqr_instance(self) -> None:
        """REGISTRY['iqr'] must be an IQR instance."""
        assert isinstance(REGISTRY["iqr"], IQR)


class TestIQRFit:
    """Tests for IQR.fit()."""

    def test_single_metric_stats(self) -> None:
        """fit() computes Q1, Q3, IQR for single METRIC column."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        table = _make_table(values)
        algo = IQR()
        algo.fit(table)

        assert "value" in algo._stats
        q1, q3, iqr = algo._stats["value"]
        # For 1..10, Q1=3.25, Q3=7.75, IQR=4.5
        assert q1 == pytest.approx(3.25)
        assert q3 == pytest.approx(7.75)
        assert iqr == pytest.approx(4.5)

    def test_multi_metric_stats(self) -> None:
        """fit() computes stats for each METRIC column independently."""
        table = _make_table({
            "cpu": [10.0, 20.0, 30.0, 40.0, 50.0],
            "mem": [1.0, 2.0, 3.0, 4.0, 5.0],
        })
        algo = IQR()
        algo.fit(table)

        assert "cpu" in algo._stats
        assert "mem" in algo._stats

    def test_constant_series_iqr_zero(self) -> None:
        """fit() on constant series produces IQR=0."""
        table = _make_table([5.0, 5.0, 5.0, 5.0, 5.0])
        algo = IQR()
        algo.fit(table)

        q1, q3, iqr = algo._stats["value"]
        assert iqr == pytest.approx(0.0)
        assert q1 == pytest.approx(5.0)
        assert q3 == pytest.approx(5.0)


class TestIQRDetect:
    """Tests for IQR.detect() output contract."""

    def test_single_metric_output_columns(self) -> None:
        """detect() output has required columns for single metric."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 100.0]
        table = _make_table(values)
        algo = IQR()
        algo.fit(table)
        result = algo.detect(table)

        expected_cols = {
            "value",
            "value.anomaly_score",
            "value.threshold_upper",
            "value.threshold_lower",
            "predicted_label",
        }
        assert set(result.df.columns) == expected_cols

    def test_multi_metric_output_columns(self) -> None:
        """detect() output has required columns for each metric + predicted_label."""
        table = _make_table({
            "cpu": [10.0, 20.0, 30.0, 40.0, 50.0, 100.0],
            "mem": [1.0, 2.0, 3.0, 4.0, 5.0, 50.0],
        })
        algo = IQR()
        algo.fit(table)
        result = algo.detect(table)

        assert "cpu" in result.df.columns
        assert "mem" in result.df.columns
        assert "cpu.anomaly_score" in result.df.columns
        assert "mem.anomaly_score" in result.df.columns
        assert "cpu.threshold_upper" in result.df.columns
        assert "mem.threshold_upper" in result.df.columns
        assert "cpu.threshold_lower" in result.df.columns
        assert "mem.threshold_lower" in result.df.columns
        assert "predicted_label" in result.df.columns

    def test_output_row_count_equals_input(self) -> None:
        """detect() output row count must equal input row count."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        table = _make_table(values)
        algo = IQR()
        algo.fit(table)
        result = algo.detect(table)

        assert len(result.df) == len(table.df)

    def test_timestamp_preserved(self) -> None:
        """detect() preserves timestamp column when input has it."""
        table = _make_table([1.0, 2.0, 3.0, 4.0, 5.0], has_timestamp=True)
        algo = IQR()
        algo.fit(table)
        result = algo.detect(table)

        assert "timestamp" in result.df.columns
        assert result.schema.columns_of(FieldRole.TIMESTAMP) == ["timestamp"]

    def test_no_timestamp_when_input_has_none(self) -> None:
        """detect() omits timestamp when input has no TIMESTAMP column."""
        table = _make_table([1.0, 2.0, 3.0, 4.0, 5.0])
        algo = IQR()
        algo.fit(table)
        result = algo.detect(table)

        assert "timestamp" not in result.df.columns

    def test_output_roles_correct(self) -> None:
        """detect() output column roles are correctly assigned."""
        table = _make_table([1.0, 2.0, 3.0, 4.0, 5.0, 100.0])
        algo = IQR()
        algo.fit(table)
        result = algo.detect(table)

        assert result.schema.roles["value"] == FieldRole.METRIC
        assert result.schema.roles["value.anomaly_score"] == FieldRole.METRIC
        assert result.schema.roles["value.threshold_upper"] == FieldRole.METRIC
        assert result.schema.roles["value.threshold_lower"] == FieldRole.METRIC
        assert result.schema.roles["predicted_label"] == FieldRole.LABEL

    def test_anomaly_detected_for_outlier(self) -> None:
        """detect() flags clear outlier as anomaly."""
        # Normal range 1..10, outlier 100
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 100.0]
        table = _make_table(values)
        algo = IQR()
        algo.fit(table)
        result = algo.detect(table)

        # The 100.0 value must be flagged
        assert result.df["predicted_label"].iloc[-1] == 1

    def test_or_merge_multi_metric(self) -> None:
        """predicted_label uses OR-merge across metrics."""
        # cpu has outlier at index 5, mem is normal
        table = _make_table({
            "cpu": [10.0, 20.0, 30.0, 40.0, 50.0, 200.0],
            "mem": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        })
        algo = IQR()
        algo.fit(table)
        result = algo.detect(table)

        # Index 5 should be anomaly (cpu outlier)
        assert result.df["predicted_label"].iloc[5] == 1


class TestIQRThresholds:
    """Tests for IQR threshold computation."""

    def test_threshold_values_correct(self) -> None:
        """threshold_upper = Q3 + k*IQR, threshold_lower = Q1 - k*IQR."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        table = _make_table(values)
        algo = IQR(k=1.5)
        algo.fit(table)
        result = algo.detect(table)

        q1, q3, iqr = algo._stats["value"]
        expected_upper = q3 + 1.5 * iqr
        expected_lower = q1 - 1.5 * iqr

        assert result.df["value.threshold_upper"].iloc[0] == pytest.approx(expected_upper)
        assert result.df["value.threshold_lower"].iloc[0] == pytest.approx(expected_lower)

    def test_custom_k_parameter(self) -> None:
        """IQR with custom k=3.0 produces wider thresholds."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        table = _make_table(values)
        algo = IQR(k=3.0)
        algo.fit(table)
        result = algo.detect(table)

        q1, q3, iqr = algo._stats["value"]
        expected_upper = q3 + 3.0 * iqr
        expected_lower = q1 - 3.0 * iqr

        assert result.df["value.threshold_upper"].iloc[0] == pytest.approx(expected_upper)
        assert result.df["value.threshold_lower"].iloc[0] == pytest.approx(expected_lower)

    def test_default_k_is_1_5(self) -> None:
        """Default k=1.5."""
        algo = IQR()
        assert algo._k == 1.5


class TestIQRIQRZeroDegradation:
    """Tests for IQR=0 (constant series) degradation handling."""

    def test_constant_series_threshold_equals_q(self) -> None:
        """When IQR=0, thresholds degrade to [Q1, Q3] = [const, const]."""
        table = _make_table([5.0, 5.0, 5.0, 5.0, 5.0])
        algo = IQR()
        algo.fit(table)
        result = algo.detect(table)

        # Threshold = Q1 - 0 = Q1, Q3 + 0 = Q3 (both = 5.0)
        assert result.df["value.threshold_upper"].iloc[0] == pytest.approx(5.0)
        assert result.df["value.threshold_lower"].iloc[0] == pytest.approx(5.0)

    def test_constant_series_no_anomalies(self) -> None:
        """When IQR=0 and values equal constant, no anomalies detected."""
        table = _make_table([5.0, 5.0, 5.0, 5.0, 5.0])
        algo = IQR()
        algo.fit(table)
        result = algo.detect(table)

        assert result.df["predicted_label"].sum() == 0

    def test_constant_series_outlier_detected(self) -> None:
        """When IQR=0 but a value differs, that point is anomaly."""
        # All 5.0 except one 10.0 — threshold is [5.0, 5.0]
        table = _make_table([5.0, 5.0, 10.0, 5.0, 5.0])
        algo = IQR()
        algo.fit(table)
        result = algo.detect(table)

        assert result.df["predicted_label"].iloc[2] == 1

    def test_iqr_zero_anomaly_score_not_nan(self) -> None:
        """Anomaly score must not be NaN when IQR=0."""
        table = _make_table([5.0, 5.0, 5.0, 5.0, 5.0])
        algo = IQR()
        algo.fit(table)
        result = algo.detect(table)

        assert not result.df["value.anomaly_score"].isna().any()

    def test_iqr_zero_anomaly_score_for_outlier(self) -> None:
        """Anomaly score > 0 for outlier when IQR=0 (uses effective_iqr=1.0)."""
        table = _make_table([5.0, 5.0, 10.0, 5.0, 5.0])
        algo = IQR()
        algo.fit(table)
        result = algo.detect(table)

        # For outlier 10.0: score = (10.0 - 5.0) / 1.0 = 5.0
        assert result.df["value.anomaly_score"].iloc[2] > 0.0


class TestIQRAnomalyScore:
    """Tests for anomaly score computation."""

    def test_anomaly_score_zero_for_normal(self) -> None:
        """Anomaly score is 0 for values within [Q1, Q3] interquartile range."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        table = _make_table(values)
        algo = IQR()
        algo.fit(table)
        result = algo.detect(table)

        # Values within [Q1, Q3] have anomaly_score = 0
        q1, q3, iqr = algo._stats["value"]
        for i, val in enumerate(values):
            if q1 <= val <= q3:
                assert result.df["value.anomaly_score"].iloc[i] == pytest.approx(0.0, abs=1e-10)

    def test_anomaly_score_positive_for_outlier(self) -> None:
        """Anomaly score is positive for values outside threshold bounds."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 100.0]
        table = _make_table(values)
        algo = IQR()
        algo.fit(table)
        result = algo.detect(table)

        # The 100.0 outlier should have positive anomaly score
        assert result.df["value.anomaly_score"].iloc[-1] > 0.0

    def test_anomaly_score_not_nan(self) -> None:
        """Anomaly score must not contain NaN values."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        table = _make_table(values)
        algo = IQR()
        algo.fit(table)
        result = algo.detect(table)

        assert not result.df["value.anomaly_score"].isna().any()


class TestIQRProtocolCompliance:
    """Tests for IQR AnomalyDetector protocol compliance."""

    def test_name_attribute(self) -> None:
        """IQR.name must be 'iqr'."""
        assert IQR.name == "iqr"

    def test_task_type_attribute(self) -> None:
        """IQR.task_type must be ANOMALY_DETECTION."""
        assert IQR.task_type == TaskType.ANOMALY_DETECTION

    def test_required_input_roles(self) -> None:
        """IQR.required_input_roles must be {METRIC}."""
        assert IQR.required_input_roles == {FieldRole.METRIC}
