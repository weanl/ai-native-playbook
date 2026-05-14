"""Integration tests for multi-algorithm DatasetBundle batch runs."""

import json
from pathlib import Path

import pandas as pd

from nextaiops_algo.core.experiment import BatchStatus, RunStatus
from nextaiops_algo.pipeline.batch_bundle import run_batch_bundle
from nextaiops_algo.pipeline.dataset_bundle import load_dataset_bundle
from nextaiops_algo.storage.sqlite_tracking import SqliteTrackingStore


def _write_experiment_csv(path: Path, anomaly_offset: int) -> Path:
    labels = [0] * 100
    values = [float(i) + 10.0 for i in range(100)]
    for idx in [80 + anomaly_offset, 81 + anomaly_offset, 82 + anomaly_offset]:
        labels[idx] = 1
        values[idx] = 100.0

    pd.DataFrame(
        {
            "timestamp": list(range(100)),
            "value": values,
            "is_anomaly": labels,
        }
    ).to_csv(path, index=False)
    return path


def test_run_batch_bundle_runs_algorithms_for_each_file_and_writes_summary(
    tmp_path: Path,
) -> None:
    """DatasetBundle batch runs all cells, persists runs, and writes summary artifacts."""
    bundle = load_dataset_bundle(
        [
            _write_experiment_csv(tmp_path / "a.csv", anomaly_offset=0),
            _write_experiment_csv(tmp_path / "b.csv", anomaly_offset=1),
        ],
        dataset_id="batch-two-files",
    )

    result = run_batch_bundle(
        bundle=bundle,
        algorithms=["three_sigma", "iqr"],
        output_dir=tmp_path / "artifacts",
        split_ratio=0.7,
    )

    assert result.status == BatchStatus.COMPLETED
    assert result.file_names == ["a.csv", "b.csv"]
    assert result.algorithm_names == ["three_sigma", "iqr"]
    assert len(result.cells) == 4
    assert all(cell.status == RunStatus.COMPLETED for cell in result.cells)
    assert result.algorithm_metrics["three_sigma"]["success_rate"] == 1.0
    assert "mean_pa_f1" in result.algorithm_metrics["three_sigma"]

    summary_path = Path(result.artifacts_path) / "batch_bundle_summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text())
    assert summary["file_count"] == 2
    assert len(summary["cells"]) == 4

    store = SqliteTrackingStore()
    for cell in result.cells:
        assert cell.run_result is not None
        run = store.get_run(cell.run_result.run_id)
        assert run is not None
        assert run.dataset_version == cell.file_name
        assert (Path(cell.run_result.artifacts_path) / "viz.html").exists()
