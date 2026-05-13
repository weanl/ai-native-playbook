"""Unit tests for viz/timeseries.py."""

import tempfile
from pathlib import Path

import pandas as pd

from nextaiops_algo.core.table import FieldRole, Table, TableSchema
from nextaiops_algo.viz.timeseries import plot_timeseries


def _make_output_table(
    n_rows: int,
    with_timestamp: bool = True,
    with_thresholds: bool = True,
    n_metrics: int = 1,
) -> Table:
    """Helper to create a detection output table."""
    df_data: dict[str, list] = {}

    if with_timestamp:
        df_data["timestamp"] = list(range(n_rows))

    # Original metric columns
    for i in range(n_metrics):
        metric_name = "value" if i == 0 else f"value{i}"
        df_data[metric_name] = [float(j) + i * 10 for j in range(n_rows)]

        if with_thresholds:
            df_data[f"{metric_name}.threshold_upper"] = [
                float(j) + i * 10 + 5.0 for j in range(n_rows)
            ]
            df_data[f"{metric_name}.threshold_lower"] = [
                float(j) + i * 10 - 5.0 for j in range(n_rows)
            ]

    # Predicted label with some anomalies
    df_data["predicted_label"] = [0] * n_rows
    if n_rows >= 5:
        df_data["predicted_label"][2] = 1  # Mark index 2 as anomaly

    df = pd.DataFrame(df_data)

    # Build schema
    roles: dict[str, FieldRole] = {}
    if with_timestamp:
        roles["timestamp"] = FieldRole.TIMESTAMP
    for i in range(n_metrics):
        metric_name = "value" if i == 0 else f"value{i}"
        roles[metric_name] = FieldRole.METRIC
        if with_thresholds:
            roles[f"{metric_name}.threshold_upper"] = FieldRole.METRIC
            roles[f"{metric_name}.threshold_lower"] = FieldRole.METRIC
    roles["predicted_label"] = FieldRole.LABEL

    schema = TableSchema(roles=roles)
    return Table(df=df, schema=schema)


def _make_input_table_for_output(n_rows: int) -> Table:
    """Create aligned input table with true labels for visualization tests."""
    labels = [0] * n_rows
    if n_rows >= 6:
        labels[2] = 1
        labels[3] = 1

    df = pd.DataFrame({"value": [float(i) for i in range(n_rows)], "label": labels})
    schema = TableSchema(roles={"value": FieldRole.METRIC, "label": FieldRole.LABEL})
    return Table(df=df, schema=schema)


class TestPlotTimeseries:
    """Tests for plot_timeseries function."""

    def test_generates_html_string(self) -> None:
        """Test that HTML string is generated."""
        table = _make_output_table(10)
        html = plot_timeseries(table)

        assert isinstance(html, str)
        assert len(html) > 0
        assert "plotly-graph-div" in html

    def test_saves_to_file(self) -> None:
        """Test that HTML can be saved to file."""
        table = _make_output_table(10)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "viz.html"
            html = plot_timeseries(table, output_path)

            assert output_path.exists()
            assert output_path.stat().st_size > 0
            assert html == output_path.read_text()

    def test_single_metric_subplot(self) -> None:
        """Test single metric creates one subplot."""
        table = _make_output_table(10, n_metrics=1)
        html = plot_timeseries(table)

        assert "value" in html
        assert "plotly-graph-div" in html

    def test_multi_metric_subplots(self) -> None:
        """Test multiple metrics create multiple subplots."""
        table = _make_output_table(10, n_metrics=2)
        html = plot_timeseries(table)

        assert "value" in html
        assert "value1" in html
        assert "Time Series Anomaly Detection" in html

    def test_without_timestamp(self) -> None:
        """Test graceful degradation without timestamp."""
        table = _make_output_table(10, with_timestamp=False)
        html = plot_timeseries(table)

        assert "plotly-graph-div" in html
        # Should use index as x-axis

    def test_without_thresholds(self) -> None:
        """Test graceful degradation without thresholds."""
        table = _make_output_table(10, with_thresholds=False)
        html = plot_timeseries(table)

        assert "plotly-graph-div" in html
        # Should not have threshold lines

    def test_anomaly_markers_visible(self) -> None:
        """Test that anomaly markers are added."""
        table = _make_output_table(10)
        html = plot_timeseries(table)

        assert "Anomaly" in html
        assert "red" in html  # Color for anomaly markers

    def test_ground_truth_classification_markers_visible(self) -> None:
        """When input labels are provided, TP/FP/FN markers are rendered."""
        table = _make_output_table(10)
        input_table = _make_input_table_for_output(10)
        html = plot_timeseries(table, input_table=input_table)

        assert "TP" in html
        assert "FP" in html
        assert "FN" in html
        assert "class=TP" in html

    def test_interactive_layout_options_present(self) -> None:
        """Timeseries HTML includes unified hover and polished background."""
        table = _make_output_table(10)
        html = plot_timeseries(table)

        assert "x unified" in html
        assert "#f8fafc" in html

    def test_file_size_greater_than_zero(self) -> None:
        """Test that saved file has positive size."""
        table = _make_output_table(10)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "viz.html"
            plot_timeseries(table, output_path)

            assert output_path.stat().st_size > 1000  # Plotly HTML is substantial
