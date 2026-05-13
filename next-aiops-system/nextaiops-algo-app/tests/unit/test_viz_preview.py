"""Unit tests for viz/preview.py."""

import pandas as pd
import pytest

from nextaiops_algo.core.table import FieldRole, Table, TableSchema
from nextaiops_algo.viz.preview import render_data_preview


def _make_table(with_timestamp: bool = True, with_label: bool = True) -> Table:
    """Create an input table for preview tests."""
    data: dict[str, list[object]] = {
        "value": [1.0, 2.0, 3.0, 10.0, 11.0, 4.0],
        "cpu": [20.0, 21.0, 22.0, 30.0, 31.0, 23.0],
    }
    roles = {
        "value": FieldRole.METRIC,
        "cpu": FieldRole.METRIC,
    }

    if with_timestamp:
        data["timestamp"] = list(range(6))
        roles["timestamp"] = FieldRole.TIMESTAMP

    if with_label:
        data["is_anomaly"] = [0, 0, 0, 1, 1, 0]
        roles["is_anomaly"] = FieldRole.LABEL

    return Table(df=pd.DataFrame(data), schema=TableSchema(roles=roles))


def test_render_data_preview_generates_figure() -> None:
    """render_data_preview() returns a Plotly figure for default metric."""
    fig = render_data_preview(_make_table())

    assert fig.layout.title.text == "Data Preview: value"
    assert len(fig.data) == 2


def test_render_data_preview_metric_selector() -> None:
    """render_data_preview() can render a selected metric column."""
    fig = render_data_preview(_make_table(), metric_name="cpu")

    assert fig.layout.title.text == "Data Preview: cpu"
    assert fig.data[0].name == "cpu"


def test_render_data_preview_without_label_degrades() -> None:
    """Tables without labels render only the metric line."""
    fig = render_data_preview(_make_table(with_label=False))

    assert len(fig.data) == 1
    assert fig.data[0].name == "value"


def test_render_data_preview_without_timestamp_uses_index() -> None:
    """Tables without timestamp use index on the x axis."""
    fig = render_data_preview(_make_table(with_timestamp=False))

    assert fig.layout.xaxis.title.text == "Index"


def test_render_data_preview_adds_anomaly_bands() -> None:
    """Labeled anomaly segments are shown as vertical bands."""
    fig = render_data_preview(_make_table())

    assert fig.layout.shapes is not None
    assert len(fig.layout.shapes) == 1


def test_render_data_preview_uses_interactive_layout() -> None:
    """Preview chart enables hover and a clean plot background."""
    fig = render_data_preview(_make_table())

    assert fig.layout.hovermode == "x unified"
    assert fig.layout.plot_bgcolor == "#f8fafc"


def test_render_data_preview_rejects_unknown_metric() -> None:
    """Unknown metric names fail fast."""
    with pytest.raises(ValueError, match="Unknown metric column"):
        render_data_preview(_make_table(), metric_name="missing")
