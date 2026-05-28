"""Unit tests for rolling bundle execution."""

from pathlib import Path

import pandas as pd

from nextaiops_algo.pipeline.dataset_bundle import load_dataset_bundle
from nextaiops_algo.pipeline.rolling import AlgorithmConfig, ExperimentPolicy
from nextaiops_algo.pipeline.rolling_bundle import run_rolling_bundle


def _write_three_day_csv(path: Path) -> None:
    rows = []
    for day in range(1, 4):
        for hour in range(10):
            is_anomaly = hour >= 8
            rows.append({
                "timestamp": f"2024-01-0{day}T{hour:02d}:00:00Z",
                "value": 100.0 if is_anomaly else float(10 + hour % 2),
                "is_anomaly": 1 if is_anomaly else 0,
            })
    pd.DataFrame(rows).to_csv(path, index=False)


def test_rolling_bundle_runs_each_file_independently(tmp_path: Path) -> None:
    file_a = tmp_path / "metric_a.csv"
    file_b = tmp_path / "metric_b.csv"
    _write_three_day_csv(file_a)
    _write_three_day_csv(file_b)

    bundle = load_dataset_bundle([file_a, file_b], dataset_id="test_bundle")
    algorithms = [AlgorithmConfig(name="three_sigma")]

    result = run_rolling_bundle(
        bundle,
        algorithms=algorithms,
        policy=ExperimentPolicy(validate_ratio=0.7),
    )

    assert result.dataset_id == "test_bundle"
    assert len(result.file_names) == 2
    assert len(result.cells) == 2
    assert all(cell.result is not None for cell in result.cells)
    assert all(cell.status == "completed" for cell in result.cells)


def test_rolling_bundle_aggregates_algorithm_metrics(tmp_path: Path) -> None:
    file_a = tmp_path / "metric_a.csv"
    file_b = tmp_path / "metric_b.csv"
    _write_three_day_csv(file_a)
    _write_three_day_csv(file_b)

    bundle = load_dataset_bundle([file_a, file_b], dataset_id="test_bundle")
    algorithms = [AlgorithmConfig(name="three_sigma")]

    result = run_rolling_bundle(
        bundle,
        algorithms=algorithms,
        policy=ExperimentPolicy(validate_ratio=0.7),
    )

    assert "three_sigma" in result.algorithm_metrics
    metrics = result.algorithm_metrics["three_sigma"]
    assert "mean_pa_f1" in metrics
    assert "median_pa_f1" in metrics
    assert "success_rate" in metrics
    assert metrics["file_count"] == 2.0


def test_rolling_bundle_handles_partial_failure(tmp_path: Path) -> None:
    file_a = tmp_path / "metric_a.csv"
    _write_three_day_csv(file_a)

    bundle = load_dataset_bundle([file_a], dataset_id="test_bundle")
    algorithms = [
        AlgorithmConfig(name="three_sigma"),
        AlgorithmConfig(name="nonexistent_algo"),
    ]

    result = run_rolling_bundle(
        bundle,
        algorithms=algorithms,
        policy=ExperimentPolicy(validate_ratio=0.7),
    )

    # The file should still succeed because rolling experiment handles
    # per-algorithm failures internally (partial_failed status)
    assert len(result.cells) == 1
    cell = result.cells[0]
    assert cell.result is not None
    # The rolling experiment itself should have partial_failed status
    # because one algorithm doesn't exist
    assert cell.status in ("completed", "partial_failed")


def test_rolling_bundle_progress_callback(tmp_path: Path) -> None:
    file_a = tmp_path / "metric_a.csv"
    file_b = tmp_path / "metric_b.csv"
    _write_three_day_csv(file_a)
    _write_three_day_csv(file_b)

    bundle = load_dataset_bundle([file_a, file_b], dataset_id="test_bundle")
    algorithms = [AlgorithmConfig(name="three_sigma")]

    progress_calls: list[tuple[int, int, str]] = []

    def progress_callback(current: int, total: int, file_name: str) -> None:
        progress_calls.append((current, total, file_name))

    run_rolling_bundle(
        bundle,
        algorithms=algorithms,
        policy=ExperimentPolicy(validate_ratio=0.7),
        progress_callback=progress_callback,
    )

    assert len(progress_calls) == 2
    assert progress_calls[0] == (1, 2, "metric_a.csv")
    assert progress_calls[1] == (2, 2, "metric_b.csv")


def test_rolling_bundle_rejects_empty_algorithms(tmp_path: Path) -> None:
    file_a = tmp_path / "metric_a.csv"
    _write_three_day_csv(file_a)

    bundle = load_dataset_bundle([file_a], dataset_id="test_bundle")

    try:
        run_rolling_bundle(bundle, algorithms=[])
    except ValueError as exc:
        assert "algorithms must not be empty" in str(exc)
    else:
        raise AssertionError("Expected ValueError for empty algorithms")
