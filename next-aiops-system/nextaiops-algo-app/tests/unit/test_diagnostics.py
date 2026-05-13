"""Unit tests for pipeline/diagnostics.py."""

import pandas as pd
import pytest

from nextaiops_algo.core.exceptions import SchemaValidationError
from nextaiops_algo.core.table import FieldRole, Table, TableSchema
from nextaiops_algo.pipeline.diagnostics import diagnose_detection


def _make_input(labels: list[int]) -> Table:
    """Create input table with labels."""
    df = pd.DataFrame({"value": list(range(len(labels))), "label": labels})
    schema = TableSchema(roles={"value": FieldRole.METRIC, "label": FieldRole.LABEL})
    return Table(df=df, schema=schema)


def _make_output(predicted: list[int]) -> Table:
    """Create output table with predicted labels."""
    df = pd.DataFrame({"value": list(range(len(predicted))), "predicted_label": predicted})
    schema = TableSchema(roles={"value": FieldRole.METRIC, "predicted_label": FieldRole.LABEL})
    return Table(df=df, schema=schema)


def test_diagnose_detection_counts_point_classes() -> None:
    """Diagnostics counts TP/FP/FN/TN and anomaly totals."""
    diagnostics = diagnose_detection(
        _make_input([0, 1, 1, 0, 1, 0]),
        _make_output([0, 1, 0, 1, 1, 0]),
    )

    assert diagnostics.true_anomalies == 3
    assert diagnostics.predicted_anomalies == 3
    assert diagnostics.tp == 2
    assert diagnostics.fp == 1
    assert diagnostics.fn == 1
    assert diagnostics.tn == 2


def test_diagnose_detection_counts_segment_hits() -> None:
    """Any prediction inside a true segment counts that segment as hit."""
    diagnostics = diagnose_detection(
        _make_input([0, 1, 1, 0, 1, 1, 1, 0]),
        _make_output([0, 0, 1, 0, 0, 0, 0, 0]),
    )

    assert diagnostics.true_segments == 2
    assert diagnostics.hit_segments == 1


def test_diagnostics_to_dict_is_json_ready() -> None:
    """to_dict() returns plain integer values."""
    diagnostics = diagnose_detection(_make_input([1, 0]), _make_output([1, 1]))

    assert diagnostics.to_dict()["tp"] == 1
    assert diagnostics.to_dict()["fp"] == 1


def test_diagnose_detection_requires_true_labels() -> None:
    """Diagnostics fail fast without ground-truth labels."""
    input_table = Table(
        df=pd.DataFrame({"value": [1.0, 2.0]}),
        schema=TableSchema(roles={"value": FieldRole.METRIC}),
    )

    with pytest.raises(SchemaValidationError, match="ground truth"):
        diagnose_detection(input_table, _make_output([0, 1]))


def test_diagnose_detection_requires_predicted_label() -> None:
    """Diagnostics fail fast without predicted labels."""
    output_table = Table(
        df=pd.DataFrame({"value": [1.0, 2.0]}),
        schema=TableSchema(roles={"value": FieldRole.METRIC}),
    )

    with pytest.raises(SchemaValidationError, match="predicted_label"):
        diagnose_detection(_make_input([0, 1]), output_table)
