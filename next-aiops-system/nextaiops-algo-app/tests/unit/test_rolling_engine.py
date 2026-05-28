from pathlib import Path

import pandas as pd

from nextaiops_algo.pipeline.rolling import (
    AlgorithmConfig,
    ExperimentPolicy,
    run_rolling_experiment,
)
from nextaiops_algo.storage.sqlite_tracking import SqliteTrackingStore


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


def test_rolling_engine_partial_failure_and_leaderboard(tmp_path: Path) -> None:
    data_path = tmp_path / "multi_day.csv"
    _write_three_day_csv(data_path)
    store = SqliteTrackingStore(tmp_path / "tracking.db")

    result = run_rolling_experiment(
        data_path,
        algorithms=[
            AlgorithmConfig(name="three_sigma"),
            AlgorithmConfig(name="missing_algo"),
        ],
        policy=ExperimentPolicy(validate_ratio=0.7),
        store=store,
    )

    assert result.experiment.status == "partial_failed"
    assert any(c.status == "completed" for c in result.cycles)
    assert any(c.status == "partial_failed" for c in result.cycles)
    assert result.leaderboard[0].algorithm_name == "three_sigma"
    assert result.leaderboard[0].cycles_completed == 2
    assert all(row.active_model_id for row in result.ledger)
    assert store.count_rolling_predictions(result.experiment.experiment_id) == len(result.ledger)


def test_rolling_engine_rejects_empty_algorithm_list(tmp_path: Path) -> None:
    data_path = tmp_path / "multi_day.csv"
    _write_three_day_csv(data_path)

    try:
        run_rolling_experiment(data_path, algorithms=[])
    except ValueError as exc:
        assert "algorithms must not be empty" in str(exc)
    else:
        raise AssertionError("Expected ValueError for empty algorithms")
