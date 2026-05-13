"""Overlay visualization — render multi-algorithm detection results on shared time axis."""

from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from nextaiops_algo.core.experiment import BatchRun, RunStatus
from nextaiops_algo.core.table import FieldRole, Table
from nextaiops_algo.storage.sqlite_tracking import SqliteTrackingStore


def render_overlay(
    batch_run: BatchRun,
    input_table: Table,
    metric_name: str | None = None,
    output_path: Path | None = None,
) -> go.Figure:
    """Render overlay comparison of multiple algorithm detection results.

    Layout:
    - Top subplot: original time series + ground truth anomaly regions
    - Below: one subplot per algorithm, showing original curve + predicted
      anomaly markers + threshold lines.

    Args:
        batch_run: BatchRun with per-algorithm ExperimentRun records.
        input_table: Original input Table (with timestamp, metric, label).
        metric_name: Which metric column to display. None uses first metric.
        output_path: Optional path to save HTML. If provided, writes file.

    Returns:
        Plotly Figure object.
    """
    store = SqliteTrackingStore()

    # Determine which metric to show
    metric_cols = input_table.schema.columns_of(FieldRole.METRIC)
    if not metric_cols:
        raise ValueError("Input table has no METRIC columns.")
    chosen_metric = metric_name if metric_name is not None else metric_cols[0]

    # Determine x-axis (timestamp or index)
    ts_col = input_table.schema.columns_of(FieldRole.TIMESTAMP)
    if ts_col:
        x_raw = input_table.df[ts_col[0]]
        x = x_raw
    else:
        x = input_table.df.index

    y_raw = input_table.df[chosen_metric]

    # Ground truth labels
    label_cols = input_table.schema.columns_of(FieldRole.LABEL)
    gt_labels = input_table.df[label_cols[0]] if label_cols else None

    # Build figure with N+1 subplots (1 original + N algorithms)
    n_algos = len(batch_run.runs)
    fig = make_subplots(
        rows=n_algos + 1,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=["Original + Ground Truth"] + [
            f"{run.algorithm_name}"
            + (" (FAILED)" if run.status == RunStatus.FAILED else "")
            for run in batch_run.runs
        ],
    )

    # Top subplot: original series + ground truth shading
    fig.add_trace(
        go.Scatter(x=x, y=y_raw, mode="lines", name=chosen_metric, line={"color": "blue"}),
        row=1, col=1,
    )

    if gt_labels is not None:
        anomaly_mask = gt_labels == 1
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y_raw.where(anomaly_mask, None),
                mode="markers",
                name="Ground Truth",
                marker={"color": "gray", "size": 4, "symbol": "circle"},
            ),
            row=1, col=1,
        )

    # Per-algorithm subplots
    for idx, run in enumerate(batch_run.runs, start=2):
        if run.status == RunStatus.FAILED:
            # Show flat line with "FAILED" annotation
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=[None] * len(x),
                    mode="text",
                    name=f"{run.algorithm_name} (FAILED)",
                    text=["FAILED"] * len(x),
                    textposition="middle center",
                ),
                row=idx, col=1,
            )
            continue

        # Load detect output from artifacts
        try:
            result_table = _load_detect_output(run, store)
        except Exception:
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=[None] * len(x),
                    mode="text",
                    name=f"{run.algorithm_name} (no output)",
                    text=["No output"] * len(x),
                    textposition="middle center",
                ),
                row=idx, col=1,
            )
            continue

        # Original series in this subplot (light)
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y_raw,
                mode="lines",
                name=f"{run.algorithm_name} (series)",
                line={"color": "lightblue", "width": 1},
                showlegend=False,
            ),
            row=idx, col=1,
        )

        # Predicted anomaly markers
        pred_label_col = result_table.schema.columns_of(FieldRole.LABEL)
        if pred_label_col:
            pred_labels = result_table.df[pred_label_col[0]]
            anomaly_mask = pred_labels == 1
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=y_raw.where(anomaly_mask, None),
                    mode="markers",
                    name=f"{run.algorithm_name} anomalies",
                    marker={"color": "red", "size": 6, "symbol": "diamond"},
                ),
                row=idx, col=1,
            )

        # Threshold lines
        upper_col = f"{chosen_metric}.threshold_upper"
        lower_col = f"{chosen_metric}.threshold_lower"

        if upper_col in result_table.df.columns:
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=result_table.df[upper_col],
                    mode="lines",
                    name=f"{run.algorithm_name} upper",
                    line={"color": "green", "width": 1, "dash": "dash"},
                    showlegend=False,
                ),
                row=idx, col=1,
            )

        if lower_col in result_table.df.columns:
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=result_table.df[lower_col],
                    mode="lines",
                    name=f"{run.algorithm_name} lower",
                    line={"color": "green", "width": 1, "dash": "dash"},
                    showlegend=False,
                ),
                row=idx, col=1,
            )

    fig.update_layout(
        height=300 * (n_algos + 1),
        title_text=f"Batch Overlay: {batch_run.batch_id}",
        showlegend=True,
    )

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(fig.to_html(), encoding="utf-8")

    return fig


def _load_detect_output(run: object, store: SqliteTrackingStore) -> Table:
    """Load the detect output Table for a completed run.

    Reads the viz.html artifact or reconstructs from stored data.
    Falls back to re-running detect if needed (not ideal but functional).
    """
    from nextaiops_algo.core.experiment import ExperimentRun

    assert isinstance(run, ExperimentRun)

    # The detect output is saved alongside viz.html in the artifacts path.
    # We reconstruct from the CSV output that was saved during run_experiment.
    artifacts_path = Path(run.artifacts_path)
    detect_csv = artifacts_path / "detect_output.csv"

    if detect_csv.exists():
        from nextaiops_algo.pipeline.preprocess import read_csv_to_table
        return read_csv_to_table(detect_csv)

    # Fallback: if we can't find the CSV, construct a minimal table
    # from the stored metrics. This won't have full detect output.
    raise FileNotFoundError(f"Detect output not found for run {run.run_id}")
