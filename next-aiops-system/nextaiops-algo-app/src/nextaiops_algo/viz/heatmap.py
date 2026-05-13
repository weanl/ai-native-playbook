"""Heatmap visualization — render algorithm × metrics matrix as Plotly heatmap."""

from pathlib import Path

import plotly.graph_objects as go

from nextaiops_algo.core.experiment import BatchRun, RunStatus
from nextaiops_algo.storage.sqlite_tracking import SqliteTrackingStore

_METRIC_KEYS = [
    "precision",
    "recall",
    "f1",
    "pa_precision",
    "pa_recall",
    "pa_f1",
]

_DISPLAY_NAMES = [
    "Precision",
    "Recall",
    "F1",
    "PA-Precision",
    "PA-Recall",
    "PA-F1",
]


def render_heatmap(
    batch_run: BatchRun,
    metrics: list[str] | None = None,
    output_path: Path | None = None,
    store: SqliteTrackingStore | None = None,
) -> go.Figure:
    """Render algorithm × metrics heatmap from a BatchRun.

    X-axis: metric names, Y-axis: algorithm names.
    Cell values are the metric scores, color-coded (RdYlGn).
    FAILED algorithms show NaN / gray.

    Args:
        batch_run: BatchRun with per-algorithm ExperimentRun records.
        metrics: Optional list of metric keys to include. None uses all 6.
        output_path: Optional path to save HTML.
        store: Optional SqliteTrackingStore instance. If None, creates default.

    Returns:
        Plotly Figure object.
    """
    if store is None:
        store = SqliteTrackingStore()

    metric_keys = metrics if metrics is not None else _METRIC_KEYS
    display_names = [
        _DISPLAY_NAMES[_METRIC_KEYS.index(k)] if k in _METRIC_KEYS else k
        for k in metric_keys
    ]

    algo_names: list[str] = []
    z_values: list[list[float]] = []

    for run in batch_run.runs:
        algo_names.append(run.algorithm_name)

        if run.status == RunStatus.COMPLETED:
            stored_metrics = store.get_metrics(run.run_id)
            row = [stored_metrics.get(k, float("nan")) for k in metric_keys]
        else:
            row = [float("nan")] * len(metric_keys)

        z_values.append(row)

    fig = go.Figure(
        data=go.Heatmap(
            z=z_values,
            x=display_names,
            y=algo_names,
            text=[[f"{v:.2f}" if v != float("nan") else "N/A" for v in row] for row in z_values],
            texttemplate="%{text}",
            coloraxis="coloraxis",
            hovertemplate="Algorithm: %{y}<br>Metric: %{x}<br>Value: %{z:.3f}<extra></extra>",
        ),
    )

    fig.update_layout(
        coloraxis={
            "colorscale": "RdYlGn",
            "cmin": 0,
            "cmax": 1,
        },
        title_text=f"Algorithm × Metrics Heatmap: {batch_run.batch_id}",
        xaxis_title="Metrics",
        yaxis_title="Algorithms",
    )

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(fig.to_html(), encoding="utf-8")

    return fig
