"""Unit tests for pipeline/evaluate.py."""

import pandas as pd
import pytest
from sklearn.metrics import f1_score, precision_score, recall_score

from nextaiops_algo.core.exceptions import SchemaValidationError
from nextaiops_algo.core.table import FieldRole, Table, TableSchema
from nextaiops_algo.pipeline.evaluate import evaluate


def _make_table(
    values: list[float],
    labels: list[int] | None = None,
    predicted: list[int] | None = None,
) -> tuple[Table, Table]:
    """Helper to create input and output tables for testing."""
    df_input = pd.DataFrame({"value": values})
    if labels is not None:
        df_input["label"] = labels

    schema_input = TableSchema(
        roles={"value": FieldRole.METRIC, "label": FieldRole.LABEL}
        if labels is not None
        else {"value": FieldRole.METRIC}
    )
    input_table = Table(df=df_input, schema=schema_input)

    # Output table
    df_output = pd.DataFrame({"value": values, "predicted_label": predicted or [0] * len(values)})
    schema_output = TableSchema(
        roles={
            "value": FieldRole.METRIC,
            "predicted_label": FieldRole.LABEL,
        }
    )
    output_table = Table(df=df_output, schema=schema_output)

    return input_table, output_table


class TestEvaluate:
    """Tests for evaluate function."""

    def test_returns_eight_keys(self) -> None:
        """evaluate() returns dict with exactly 8 metric keys."""
        input_table, output_table = _make_table(
            values=[10.0, 15.0, 20.0],
            labels=[0, 1, 0],
            predicted=[0, 1, 0],
        )
        metrics = evaluate(input_table, output_table)
        expected_keys = {
            "precision", "recall", "f1",
            "pa_precision", "pa_recall", "pa_f1",
            "seg_recall", "seg_precision",
        }
        assert set(metrics.keys()) == expected_keys

    def test_all_correct_predictions(self) -> None:
        """Test when all predictions are correct."""
        input_table, output_table = _make_table(
            values=[10.0, 15.0, 20.0],
            labels=[0, 1, 0],
            predicted=[0, 1, 0],
        )
        metrics = evaluate(input_table, output_table)
        assert metrics["precision"] == 1.0
        assert metrics["recall"] == 1.0
        assert metrics["f1"] == 1.0
        assert metrics["pa_precision"] == 1.0
        assert metrics["pa_recall"] == 1.0
        assert metrics["pa_f1"] == 1.0

    def test_some_false_positives(self) -> None:
        """Test with false positives."""
        input_table, output_table = _make_table(
            values=[10.0, 15.0, 20.0, 25.0],
            labels=[0, 1, 0, 0],
            predicted=[1, 1, 0, 1],  # FP at index 0 and 3
        )
        metrics = evaluate(input_table, output_table)
        # TP=1, FP=2 => precision = 1/3 = 0.333
        # Recall = 1/1 = 1.0
        assert metrics["precision"] == pytest.approx(1 / 3)
        assert metrics["recall"] == 1.0

    def test_some_false_negatives(self) -> None:
        """Test with false negatives."""
        input_table, output_table = _make_table(
            values=[10.0, 15.0, 20.0, 25.0],
            labels=[1, 1, 0, 0],
            predicted=[0, 1, 0, 0],  # FN at index 0
        )
        metrics = evaluate(input_table, output_table)
        # TP=1, FN=1 => recall = 1/2 = 0.5
        # Precision = 1/1 = 1.0
        assert metrics["precision"] == 1.0
        assert metrics["recall"] == pytest.approx(0.5)

    def test_no_anomalies_predicted_or_true(self) -> None:
        """Test when no anomalies exist — all zeros."""
        input_table, output_table = _make_table(
            values=[10.0, 15.0, 20.0],
            labels=[0, 0, 0],
            predicted=[0, 0, 0],
        )
        metrics = evaluate(input_table, output_table)
        # TP=0, FP=0, FN=0 => zero_division=0
        assert metrics["precision"] == 0.0
        assert metrics["recall"] == 0.0
        assert metrics["f1"] == 0.0
        assert metrics["pa_precision"] == 0.0
        assert metrics["pa_recall"] == 0.0
        assert metrics["pa_f1"] == 0.0

    def test_no_true_labels_raises_error(self) -> None:
        """Missing LABEL column must raise SchemaValidationError."""
        input_table, output_table = _make_table(
            values=[10.0, 15.0, 20.0],
            labels=None,  # No ground truth
            predicted=[0, 1, 0],
        )
        with pytest.raises(SchemaValidationError, match="no LABEL"):
            evaluate(input_table, output_table)

    def test_missing_predicted_label_raises_error(self) -> None:
        """Missing predicted_label column must raise SchemaValidationError."""
        df_input = pd.DataFrame({"value": [10.0], "label": [0]})
        schema_input = TableSchema(roles={"value": FieldRole.METRIC, "label": FieldRole.LABEL})
        input_table = Table(df=df_input, schema=schema_input)

        # Output without predicted_label
        df_output = pd.DataFrame({"value": [10.0]})
        schema_output = TableSchema(roles={"value": FieldRole.METRIC})
        output_table = Table(df=df_output, schema=schema_output)

        with pytest.raises(SchemaValidationError, match="predicted_label"):
            evaluate(input_table, output_table)

    def test_f1_calculation(self) -> None:
        """Test F1 = 2 * P * R / (P + R)."""
        input_table, output_table = _make_table(
            values=[10.0, 15.0, 20.0, 25.0],
            labels=[1, 1, 0, 0],
            predicted=[1, 0, 1, 0],  # TP=1, FP=1, FN=1
        )
        metrics = evaluate(input_table, output_table)
        # P=1/2=0.5, R=1/2=0.5, F1=2*0.5*0.5/(0.5+0.5)=0.5
        assert metrics["precision"] == pytest.approx(0.5)
        assert metrics["recall"] == pytest.approx(0.5)
        assert metrics["f1"] == pytest.approx(0.5)

    def test_standard_metrics_match_sklearn(self) -> None:
        """Standard P/R/F1 must match sklearn results."""
        labels = [0, 1, 0, 1, 1, 0, 0, 1, 0, 1]
        predicted = [0, 1, 1, 0, 1, 0, 1, 1, 0, 0]
        input_table, output_table = _make_table(
            values=[float(i) for i in range(len(labels))],
            labels=labels,
            predicted=predicted,
        )
        metrics = evaluate(input_table, output_table)

        assert metrics["precision"] == pytest.approx(
            precision_score(labels, predicted, zero_division=0)
        )
        assert metrics["recall"] == pytest.approx(
            recall_score(labels, predicted, zero_division=0)
        )
        assert metrics["f1"] == pytest.approx(
            f1_score(labels, predicted, zero_division=0)
        )

    def test_all_zeros_prediction(self) -> None:
        """All predictions 0 — zero_division boundary."""
        input_table, output_table = _make_table(
            values=[10.0, 15.0, 20.0, 25.0],
            labels=[1, 1, 0, 0],
            predicted=[0, 0, 0, 0],
        )
        metrics = evaluate(input_table, output_table)
        # TP=0, FP=0, FN=2
        assert metrics["precision"] == 0.0
        assert metrics["recall"] == 0.0
        assert metrics["f1"] == 0.0
        # PA: no anomaly segment hit
        assert metrics["pa_precision"] == 0.0
        assert metrics["pa_recall"] == 0.0
        assert metrics["pa_f1"] == 0.0

    def test_all_ones_prediction(self) -> None:
        """All predictions 1 — recall=1, PA-recall=1."""
        input_table, output_table = _make_table(
            values=[10.0, 15.0, 20.0, 25.0],
            labels=[1, 1, 0, 0],
            predicted=[1, 1, 1, 1],
        )
        metrics = evaluate(input_table, output_table)
        # Standard: TP=2, FP=2, FN=0 => P=0.5, R=1.0, F1=2/3
        assert metrics["precision"] == pytest.approx(0.5)
        assert metrics["recall"] == 1.0
        assert metrics["f1"] == pytest.approx(2 / 3)
        # PA: anomaly segment hit => pa_recall=1.0
        assert metrics["pa_recall"] == 1.0
