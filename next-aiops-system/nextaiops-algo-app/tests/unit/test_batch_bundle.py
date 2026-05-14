"""Unit tests for multi-algorithm DatasetBundle batch runs."""

import json
from pathlib import Path

import pandas as pd
import pytest

from nextaiops_algo.core.experiment import BatchStatus, RunResult, RunStatus
from nextaiops_algo.pipeline.batch_bundle import run_batch_bundle
from nextaiops_algo.pipeline.dataset_bundle import load_dataset_bundle


def _write_csv(path: Path, offset: int = 0) -> Path:
    pd.DataFrame(
        {
            "timestamp": list(range(20)),
            "value": [float(index + offset) for index in range(20)],
            "is_anomaly": [0] * 18 + [1, 1],
        }
    ).to_csv(path, index=False)
    return path


def test_run_batch_bundle_returns_one_cell_per_algorithm_and_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two algorithms × two files produces four completed cells."""
    bundle = load_dataset_bundle(
        [_write_csv(tmp_path / "a.csv"), _write_csv(tmp_path / "b.csv", offset=1)],
        dataset_id="bundle",
    )

    def fake_run_experiment(
        dataset_path: str | Path,
        algorithm_name: str,
        params: dict[str, object] | None = None,
        output_dir: Path | None = None,
        split_ratio: float = 0.7,
    ) -> RunResult:
        del params, split_ratio
        artifacts_path = (output_dir or tmp_path) / f"{algorithm_name}_{Path(dataset_path).stem}"
        artifacts_path.mkdir(parents=True, exist_ok=True)
        return RunResult(
            run_id=f"{algorithm_name}_{Path(dataset_path).stem}",
            metrics={"f1": 0.5, "pa_f1": 0.75},
            artifacts_path=str(artifacts_path),
        )

    monkeypatch.setattr("nextaiops_algo.pipeline.batch_bundle.run_experiment", fake_run_experiment)

    result = run_batch_bundle(
        bundle=bundle,
        algorithms=["three_sigma", "iqr"],
        output_dir=tmp_path / "artifacts",
    )

    assert result.dataset_id == "bundle"
    assert result.status == BatchStatus.COMPLETED
    assert len(result.cells) == 4
    assert all(cell.status == RunStatus.COMPLETED for cell in result.cells)
    assert result.algorithm_metrics["three_sigma"]["mean_pa_f1"] == 0.75
    assert result.algorithm_metrics["three_sigma"]["median_pa_f1"] == 0.75
    assert result.algorithm_metrics["three_sigma"]["min_pa_f1"] == 0.75
    assert result.algorithm_metrics["three_sigma"]["success_rate"] == 1.0

    summary_path = Path(result.artifacts_path) / "batch_bundle_summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text())
    assert summary["dataset_id"] == "bundle"
    assert summary["algorithm_names"] == ["three_sigma", "iqr"]
    assert len(summary["cells"]) == 4


def test_run_batch_bundle_marks_unknown_algorithm_failed(tmp_path: Path) -> None:
    """An unknown algorithm fails each file without blocking registered algorithms."""
    bundle = load_dataset_bundle(
        [_write_csv(tmp_path / "a.csv"), _write_csv(tmp_path / "b.csv", offset=1)]
    )

    result = run_batch_bundle(
        bundle=bundle,
        algorithms=["missing_algo"],
        output_dir=tmp_path / "artifacts",
    )

    assert result.status == BatchStatus.FAILED
    assert len(result.cells) == 2
    assert all(cell.status == RunStatus.FAILED for cell in result.cells)
    assert all("not found" in (cell.error_message or "") for cell in result.cells)
    assert result.algorithm_metrics["missing_algo"]["success_rate"] == 0.0


def test_run_batch_bundle_keeps_running_after_cell_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A single file failure is isolated to that cell."""
    bundle = load_dataset_bundle(
        [_write_csv(tmp_path / "a.csv"), _write_csv(tmp_path / "b.csv", offset=1)]
    )

    def fake_run_experiment(
        dataset_path: str | Path,
        algorithm_name: str,
        params: dict[str, object] | None = None,
        output_dir: Path | None = None,
        split_ratio: float = 0.7,
    ) -> RunResult:
        del params, output_dir, split_ratio
        if Path(dataset_path).name == "b.csv":
            raise RuntimeError("bad file")
        return RunResult(
            run_id=f"{algorithm_name}_a",
            metrics={"f1": 0.25, "pa_f1": 0.5},
            artifacts_path=str(tmp_path / "run"),
        )

    monkeypatch.setattr("nextaiops_algo.pipeline.batch_bundle.run_experiment", fake_run_experiment)

    result = run_batch_bundle(
        bundle=bundle,
        algorithms=["three_sigma"],
        output_dir=tmp_path / "artifacts",
    )

    assert result.status == BatchStatus.PARTIAL_FAILED
    assert [cell.status for cell in result.cells] == [RunStatus.COMPLETED, RunStatus.FAILED]
    assert result.algorithm_metrics["three_sigma"]["success_rate"] == 0.5
    assert result.algorithm_metrics["three_sigma"]["mean_pa_f1"] == 0.5
    assert result.cells[1].error_message == "bad file"


def test_run_batch_bundle_reports_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Progress callbacks receive cell index, total, algorithm, and file."""
    bundle = load_dataset_bundle(
        [_write_csv(tmp_path / "a.csv"), _write_csv(tmp_path / "b.csv", offset=1)]
    )
    progress_events: list[tuple[int, int, str, str]] = []

    def fake_run_experiment(
        dataset_path: str | Path,
        algorithm_name: str,
        params: dict[str, object] | None = None,
        output_dir: Path | None = None,
        split_ratio: float = 0.7,
    ) -> RunResult:
        del params, output_dir, split_ratio
        return RunResult(
            run_id=f"{algorithm_name}_{Path(dataset_path).stem}",
            metrics={"f1": 0.5, "pa_f1": 0.5},
            artifacts_path=str(tmp_path / "run"),
        )

    monkeypatch.setattr("nextaiops_algo.pipeline.batch_bundle.run_experiment", fake_run_experiment)

    run_batch_bundle(
        bundle=bundle,
        algorithms=["three_sigma", "iqr"],
        output_dir=tmp_path / "artifacts",
        progress_callback=lambda index, total, algo, file_name: progress_events.append(
            (index, total, algo, file_name)
        ),
    )

    assert progress_events == [
        (1, 4, "three_sigma", "a.csv"),
        (2, 4, "three_sigma", "b.csv"),
        (3, 4, "iqr", "a.csv"),
        (4, 4, "iqr", "b.csv"),
    ]
