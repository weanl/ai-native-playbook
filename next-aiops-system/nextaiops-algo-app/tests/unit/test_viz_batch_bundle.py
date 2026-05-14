"""Unit tests for DatasetBundle batch visual helpers."""

from pathlib import Path

import pandas as pd

from nextaiops_algo.core.experiment import BatchStatus, RunResult, RunStatus
from nextaiops_algo.pipeline.batch_bundle import (
    BatchBundleCellResult,
    BatchBundleResult,
)
from nextaiops_algo.viz.batch_bundle import (
    build_file_batch_view,
    render_bundle_algorithm_leaderboard,
    render_bundle_file_matrix,
    render_bundle_heatmap,
)


def _make_result(tmp_path: Path) -> BatchBundleResult:
    cells = [
        BatchBundleCellResult(
            algorithm_name="three_sigma",
            file_name="a.csv",
            status=RunStatus.COMPLETED,
            run_result=RunResult(
                run_id="ts_a",
                metrics={"f1": 0.4, "pa_f1": 0.6},
                artifacts_path=str(tmp_path / "ts_a"),
            ),
        ),
        BatchBundleCellResult(
            algorithm_name="three_sigma",
            file_name="b.csv",
            status=RunStatus.COMPLETED,
            run_result=RunResult(
                run_id="ts_b",
                metrics={"f1": 0.6, "pa_f1": 0.8},
                artifacts_path=str(tmp_path / "ts_b"),
            ),
        ),
        BatchBundleCellResult(
            algorithm_name="iqr",
            file_name="a.csv",
            status=RunStatus.COMPLETED,
            run_result=RunResult(
                run_id="iqr_a",
                metrics={"f1": 0.5, "pa_f1": 0.7},
                artifacts_path=str(tmp_path / "iqr_a"),
            ),
        ),
        BatchBundleCellResult(
            algorithm_name="iqr",
            file_name="b.csv",
            status=RunStatus.FAILED,
            error_message="bad file",
        ),
    ]
    return BatchBundleResult(
        batch_bundle_id="bb1",
        dataset_id="bundle",
        algorithm_names=["three_sigma", "iqr"],
        file_names=["a.csv", "b.csv"],
        cells=cells,
        status=BatchStatus.PARTIAL_FAILED,
        algorithm_metrics={
            "three_sigma": {
                "mean_pa_f1": 0.7,
                "median_pa_f1": 0.7,
                "min_pa_f1": 0.6,
                "mean_f1": 0.5,
                "success_rate": 1.0,
                "success_count": 2.0,
                "file_count": 2.0,
            },
            "iqr": {
                "mean_pa_f1": 0.7,
                "median_pa_f1": 0.7,
                "min_pa_f1": 0.7,
                "mean_f1": 0.5,
                "success_rate": 0.5,
                "success_count": 1.0,
                "file_count": 2.0,
            },
        },
        file_metrics={},
        artifacts_path=str(tmp_path / "summary"),
    )


def test_render_bundle_algorithm_leaderboard_sorts_by_success_rate(tmp_path: Path) -> None:
    """Algorithm leaderboard ranks fully successful algorithms first."""
    df = render_bundle_algorithm_leaderboard(_make_result(tmp_path))

    assert list(df["Algorithm"]) == ["three_sigma", "iqr"]
    assert list(df["Success Rate"]) == [1.0, 0.5]
    assert "Mean PA-F1" in df.columns


def test_render_bundle_file_matrix_includes_failed_cell_as_nan(tmp_path: Path) -> None:
    """Algorithm × file matrix preserves failed cells as NaN values."""
    matrix = render_bundle_file_matrix(_make_result(tmp_path), metric="pa_f1")

    assert list(matrix.index) == ["three_sigma", "iqr"]
    assert list(matrix.columns) == ["a.csv", "b.csv"]
    assert matrix.loc["three_sigma", "a.csv"] == 0.6
    assert pd.isna(matrix.loc["iqr", "b.csv"])


def test_render_bundle_heatmap_generates_figure(tmp_path: Path) -> None:
    """Bundle heatmap renders one Plotly heatmap trace."""
    fig = render_bundle_heatmap(_make_result(tmp_path), metric="pa_f1")

    assert fig is not None
    assert len(fig.data) == 1
    heatmap = fig.data[0]
    assert list(heatmap.x) == ["a.csv", "b.csv"]
    assert list(heatmap.y) == ["three_sigma", "iqr"]


def test_render_bundle_heatmap_writes_html(tmp_path: Path) -> None:
    """Bundle heatmap can be saved as standalone HTML."""
    output_path = tmp_path / "heatmap.html"
    render_bundle_heatmap(_make_result(tmp_path), output_path=output_path)

    assert output_path.exists()
    assert "plotly" in output_path.read_text(encoding="utf-8").lower()


def test_build_file_batch_view_uses_only_successful_cells_for_file(tmp_path: Path) -> None:
    """File batch view adapts one file's successful cells for existing overlay code."""
    batch = build_file_batch_view(_make_result(tmp_path), file_name="a.csv")

    assert batch.dataset_source == "a.csv"
    assert batch.status == BatchStatus.COMPLETED
    assert [run.algorithm_name for run in batch.runs] == ["three_sigma", "iqr"]

    failed_file_batch = build_file_batch_view(_make_result(tmp_path), file_name="b.csv")
    assert failed_file_batch.status == BatchStatus.PARTIAL_FAILED
    assert [run.algorithm_name for run in failed_file_batch.runs] == ["three_sigma"]
