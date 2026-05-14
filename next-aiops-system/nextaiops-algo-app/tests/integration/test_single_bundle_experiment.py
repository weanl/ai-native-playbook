"""Integration tests for single-algorithm DatasetBundle experiments."""

import json
from pathlib import Path

import pandas as pd

from nextaiops_algo.pipeline.dataset_bundle import load_dataset_bundle
from nextaiops_algo.pipeline.run_bundle import run_bundle_experiment
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


def test_run_bundle_experiment_runs_each_file_and_writes_summary(tmp_path: Path) -> None:
    """A DatasetBundle runs one algorithm per file and aggregates metrics."""
    paths = [
        _write_experiment_csv(tmp_path / "a.csv", anomaly_offset=0),
        _write_experiment_csv(tmp_path / "b.csv", anomaly_offset=1),
    ]
    bundle = load_dataset_bundle(paths, dataset_id="two-files")

    result = run_bundle_experiment(
        bundle=bundle,
        algorithm_name="three_sigma",
        output_dir=tmp_path / "artifacts",
        split_ratio=0.7,
    )

    assert result.dataset_id == "two-files"
    assert len(result.file_results) == 2
    assert result.metrics["file_count"] == 2.0
    assert "f1" in result.metrics

    summary_path = Path(result.artifacts_path) / "bundle_summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text())
    assert summary["file_count"] == 2
    assert [file["file_name"] for file in summary["files"]] == ["a.csv", "b.csv"]

    store = SqliteTrackingStore()
    for file_result in result.file_results:
        run = store.get_run(file_result.run_result.run_id)
        assert run is not None
        assert run.dataset_version == file_result.file_name
        assert (Path(file_result.run_result.artifacts_path) / "viz.html").exists()
