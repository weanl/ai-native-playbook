"""Visual helpers for multi-algorithm DatasetBundle batch results."""

from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from nextaiops_algo.core.experiment import BatchRun, BatchStatus, ExperimentRun, RunStatus
from nextaiops_algo.pipeline.batch_bundle import BatchBundleCellResult, BatchBundleResult

_DISPLAY_NAMES = {
    "mean_pa_f1": "Mean PA-F1",
    "median_pa_f1": "Median PA-F1",
    "min_pa_f1": "Min PA-F1",
    "mean_f1": "Mean F1",
    "success_rate": "Success Rate",
    "success_count": "Success Count",
    "file_count": "File Count",
}


def render_bundle_algorithm_leaderboard(result: BatchBundleResult) -> pd.DataFrame:
    """Render algorithm-level aggregate metrics as a ranked DataFrame.

    Args:
        result: BatchBundleResult returned by run_batch_bundle.

    Returns:
        DataFrame sorted by success rate and mean PA-F1.
    """
    rows: list[dict[str, object]] = []
    for algorithm_name in result.algorithm_names:
        metrics = result.algorithm_metrics.get(algorithm_name, {})
        row: dict[str, object] = {"Algorithm": algorithm_name}
        for key, display_name in _DISPLAY_NAMES.items():
            row[display_name] = metrics.get(key, float("nan"))
        rows.append(row)

    df = pd.DataFrame(rows)
    sort_columns = [column for column in ["Success Rate", "Mean PA-F1"] if column in df.columns]
    if sort_columns:
        df = df.sort_values(sort_columns, ascending=[False] * len(sort_columns), na_position="last")
    return df.reset_index(drop=True)


def render_bundle_file_matrix(
    result: BatchBundleResult,
    metric: str = "pa_f1",
) -> pd.DataFrame:
    """Render an algorithm × file metric matrix.

    Args:
        result: BatchBundleResult returned by run_batch_bundle.
        metric: Metric key to display for each successful cell.

    Returns:
        DataFrame indexed by algorithm name with one column per file.
    """
    rows: list[dict[str, object]] = []
    for algorithm_name in result.algorithm_names:
        row: dict[str, object] = {"Algorithm": algorithm_name}
        for file_name in result.file_names:
            cell = _find_cell(result.cells, algorithm_name, file_name)
            row[file_name] = _cell_metric(cell, metric)
        rows.append(row)

    return pd.DataFrame(rows).set_index("Algorithm")


def render_bundle_heatmap(
    result: BatchBundleResult,
    metric: str = "pa_f1",
    output_path: Path | None = None,
) -> go.Figure:
    """Render an algorithm × file heatmap for one metric.

    Args:
        result: BatchBundleResult returned by run_batch_bundle.
        metric: Metric key to display.
        output_path: Optional path to save HTML.

    Returns:
        Plotly Figure object.
    """
    matrix = render_bundle_file_matrix(result, metric=metric)
    z_values = matrix.to_numpy(dtype=float).tolist()
    text = [
        [_format_cell(value) for value in row]
        for row in z_values
    ]

    fig = go.Figure(
        data=go.Heatmap(
            z=z_values,
            x=list(matrix.columns),
            y=list(matrix.index),
            text=text,
            texttemplate="%{text}",
            coloraxis="coloraxis",
            hovertemplate="Algorithm: %{y}<br>File: %{x}<br>"
            f"{metric}: %{{z:.3f}}<extra></extra>",
        )
    )
    fig.update_layout(
        coloraxis={"colorscale": "RdYlGn", "cmin": 0, "cmax": 1},
        title_text=f"Algorithm × File Heatmap: {result.batch_bundle_id}",
        xaxis_title="Files",
        yaxis_title="Algorithms",
    )

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(fig.to_html(), encoding="utf-8")

    return fig


def build_file_batch_view(result: BatchBundleResult, file_name: str) -> BatchRun:
    """Build a temporary BatchRun view for one file's successful cells.

    The returned object lets existing overlay visualization render multi-algorithm
    comparison for a selected file without changing the single-file BatchRun model.
    """
    cells = [
        cell
        for cell in result.cells
        if cell.file_name == file_name
        and cell.status == RunStatus.COMPLETED
        and cell.run_result is not None
    ]
    runs: list[ExperimentRun] = []
    for cell in cells:
        if cell.run_result is None:
            continue
        runs.append(
            ExperimentRun(
                run_id=cell.run_result.run_id,
                dataset_version=file_name,
                algorithm_name=cell.algorithm_name,
                params={},
                status=RunStatus.COMPLETED,
                artifacts_path=cell.run_result.artifacts_path,
                created_at=datetime.now(),
            )
        )

    if not runs:
        status = BatchStatus.FAILED
    elif len(runs) == len(result.algorithm_names):
        status = BatchStatus.COMPLETED
    else:
        status = BatchStatus.PARTIAL_FAILED

    return BatchRun(
        batch_id=f"{result.batch_bundle_id}:{file_name}",
        dataset_source=file_name,
        algorithm_names=[cell.algorithm_name for cell in cells],
        created_at=datetime.now(),
        runs=runs,
        status=status,
    )


def _find_cell(
    cells: list[BatchBundleCellResult],
    algorithm_name: str,
    file_name: str,
) -> BatchBundleCellResult | None:
    for cell in cells:
        if cell.algorithm_name == algorithm_name and cell.file_name == file_name:
            return cell
    return None


def _cell_metric(cell: BatchBundleCellResult | None, metric: str) -> float:
    if cell is None or cell.status != RunStatus.COMPLETED or cell.run_result is None:
        return float("nan")
    return cell.run_result.metrics.get(metric, float("nan"))


def _format_cell(value: float) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{value:.2f}"
