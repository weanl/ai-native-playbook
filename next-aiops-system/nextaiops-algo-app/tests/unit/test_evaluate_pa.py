"""Unit tests for Point-Adjust evaluation (point_adjust_labels + PA metrics)."""

import numpy as np
import pandas as pd
import pytest

from nextaiops_algo.core.table import FieldRole, Table, TableSchema
from nextaiops_algo.pipeline.evaluate import evaluate, point_adjust_labels


def _make_table(
    values: list[float],
    labels: list[int],
    predicted: list[int],
) -> tuple[Table, Table]:
    """Helper to create input and output tables for testing."""
    df_input = pd.DataFrame({"value": values, "label": labels})
    schema_input = TableSchema(
        roles={"value": FieldRole.METRIC, "label": FieldRole.LABEL}
    )
    input_table = Table(df=df_input, schema=schema_input)

    df_output = pd.DataFrame({"value": values, "predicted_label": predicted})
    schema_output = TableSchema(
        roles={"value": FieldRole.METRIC, "predicted_label": FieldRole.LABEL}
    )
    output_table = Table(df=df_output, schema=schema_output)

    return input_table, output_table


class TestPointAdjustLabels:
    """Tests for point_adjust_labels function."""

    def test_hit_segment_adjusts_all_points(self) -> None:
        """If any point in anomaly segment is hit, entire segment becomes TP."""
        y_true = np.array([0, 1, 1, 1, 0, 0])
        y_pred = np.array([0, 0, 1, 0, 0, 0])  # Hit at index 2 only
        adjusted = point_adjust_labels(y_true, y_pred)
        # Entire segment [1,2,3] should remain 1 (hit)
        assert adjusted[1] == 1
        assert adjusted[2] == 1
        assert adjusted[3] == 1

    def test_unhit_segment_marked_zero(self) -> None:
        """Unhit anomaly segment is marked 0 for FN counting."""
        y_true = np.array([0, 1, 1, 1, 0, 0])
        y_pred = np.array([0, 0, 0, 0, 0, 0])  # Miss entire segment
        adjusted = point_adjust_labels(y_true, y_pred)
        # Unhit segment [1,2,3] → all 0
        assert adjusted[1] == 0
        assert adjusted[2] == 0
        assert adjusted[3] == 0

    def test_multiple_segments(self) -> None:
        """Two anomaly segments: one hit, one unhit."""
        y_true = np.array([0, 1, 1, 0, 1, 1, 0])
        y_pred = np.array([0, 1, 0, 0, 0, 0, 0])  # Hit first segment only
        adjusted = point_adjust_labels(y_true, y_pred)
        # First segment [1,2] hit → kept as 1
        assert adjusted[1] == 1
        assert adjusted[2] == 1
        # Second segment [4,5] unhit → marked 0
        assert adjusted[4] == 0
        assert adjusted[5] == 0

    def test_single_point_anomaly_hit(self) -> None:
        """Single-point anomaly segment hit by prediction."""
        y_true = np.array([0, 1, 0])
        y_pred = np.array([0, 1, 0])
        adjusted = point_adjust_labels(y_true, y_pred)
        assert adjusted[1] == 1

    def test_single_point_anomaly_unhit(self) -> None:
        """Single-point anomaly segment not hit."""
        y_true = np.array([0, 1, 0])
        y_pred = np.array([0, 0, 0])
        adjusted = point_adjust_labels(y_true, y_pred)
        assert adjusted[1] == 0

    def test_all_normal_points(self) -> None:
        """No anomaly segments — adjusted equals original."""
        y_true = np.array([0, 0, 0, 0])
        y_pred = np.array([0, 0, 1, 0])  # FP at index 2
        adjusted = point_adjust_labels(y_true, y_pred)
        # No segments to adjust, stays all 0
        np.testing.assert_array_equal(adjusted, y_true)

    def test_all_true_anomalies(self) -> None:
        """Entire series is anomaly — single segment."""
        y_true = np.array([1, 1, 1, 1])
        y_pred = np.array([0, 1, 0, 0])  # Hit at index 1
        adjusted = point_adjust_labels(y_true, y_pred)
        # Entire segment hit → all remain 1
        np.testing.assert_array_equal(adjusted, y_true)


class TestPAMetrics:
    """Tests for PA-Precision, PA-Recall, PA-F1 via evaluate()."""

    def test_pa_f1_greater_than_f1_when_segment_hit(self) -> None:
        """PA-F1 > standard F1 when prediction hits anomaly segment partially."""
        # Ground truth: segment of 10 anomalies at indices 10-19
        # Prediction: hits only 1 point at index 10
        values = [float(i) for i in range(30)]
        labels = [0] * 10 + [1] * 10 + [0] * 10
        predicted = [0] * 10 + [1, 0, 0, 0, 0, 0, 0, 0, 0, 0] + [0] * 10
        input_table, output_table = _make_table(values, labels, predicted)
        metrics = evaluate(input_table, output_table)

        # Standard: TP=1, FP=0, FN=9 => P=1.0, R=0.1, F1≈0.18
        assert metrics["f1"] < 0.2
        # PA: entire segment hit => PA-TP=10, PA-FP=0, PA-FN=0 => PA-R=1.0
        assert metrics["pa_f1"] > metrics["f1"]
        assert metrics["pa_recall"] == 1.0

    def test_pa_f1_equals_f1_when_pointwise_match(self) -> None:
        """PA-F1 equals standard F1 when every anomaly point is correctly detected."""
        input_table, output_table = _make_table(
            values=[10.0, 15.0, 20.0],
            labels=[0, 1, 0],
            predicted=[0, 1, 0],
        )
        metrics = evaluate(input_table, output_table)
        assert metrics["pa_f1"] == metrics["f1"]

    def test_pa_f1_equals_f1_when_no_anomalies(self) -> None:
        """PA-F1 equals standard F1 when no anomalies in ground truth."""
        input_table, output_table = _make_table(
            values=[10.0, 15.0, 20.0],
            labels=[0, 0, 0],
            predicted=[0, 0, 0],
        )
        metrics = evaluate(input_table, output_table)
        assert metrics["pa_f1"] == metrics["f1"] == 0.0

    def test_pa_f1_greater_with_multiple_segments(self) -> None:
        """PA-F1 > F1 with two anomaly segments, both partially hit."""
        # Segments: [5,6,7] and [15,16]
        # Prediction hits 1 point in each
        values = [float(i) for i in range(25)]
        labels = [0] * 5 + [1] * 3 + [0] * 8 + [1] * 2 + [0] * 7
        predicted = [0] * 5 + [1, 0, 0] + [0] * 8 + [1, 0] + [0] * 7
        input_table, output_table = _make_table(values, labels, predicted)
        metrics = evaluate(input_table, output_table)

        # Standard: TP=2, FP=0, FN=3 => P=1.0, R=2/5=0.4, F1≈0.57
        # PA: both segments hit => PA-TP=5, PA-FP=0, PA-FN=0 => PA-R=1.0, PA-F1=1.0
        assert metrics["pa_f1"] > metrics["f1"]
        assert metrics["pa_recall"] == 1.0

    def test_pa_precision_with_fp(self) -> None:
        """PA-Precision accounts for FP (point-wise, not adjusted)."""
        # Segment [5,6,7] hit at index 5, but FP at index 10
        values = [float(i) for i in range(15)]
        labels = [0] * 5 + [1] * 3 + [0] * 7
        predicted = [0] * 5 + [1, 0, 0] + [0, 1, 0, 0, 0, 0, 0]
        input_table, output_table = _make_table(values, labels, predicted)
        metrics = evaluate(input_table, output_table)

        # Standard: TP=1, FP=1, FN=2 => P=0.5, R=1/3≈0.33
        # PA: segment hit => PA-TP=3, FP=1 => PA-P=3/4=0.75
        assert metrics["pa_precision"] > metrics["precision"]
        assert metrics["pa_precision"] == pytest.approx(3 / 4)

    def test_pa_all_zeros_prediction(self) -> None:
        """All predictions 0 — PA metrics should be 0."""
        input_table, output_table = _make_table(
            values=[10.0, 15.0, 20.0, 25.0],
            labels=[1, 1, 0, 0],
            predicted=[0, 0, 0, 0],
        )
        metrics = evaluate(input_table, output_table)
        assert metrics["pa_precision"] == 0.0
        assert metrics["pa_recall"] == 0.0
        assert metrics["pa_f1"] == 0.0

    def test_pa_all_ones_prediction(self) -> None:
        """All predictions 1 — PA-recall=1.0 (all anomaly segments hit)."""
        input_table, output_table = _make_table(
            values=[10.0, 15.0, 20.0, 25.0],
            labels=[1, 1, 0, 0],
            predicted=[1, 1, 1, 1],
        )
        metrics = evaluate(input_table, output_table)
        assert metrics["pa_recall"] == 1.0
