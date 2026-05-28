from pathlib import Path

import pandas as pd

from nextaiops_algo.pipeline.rolling import (
    AlgorithmConfig,
    ExperimentPolicy,
    run_rolling_experiment,
)
from nextaiops_algo.pipeline.rolling_data import SyntheticTimeConfig
from nextaiops_algo.storage.sqlite_tracking import SqliteTrackingStore


def test_rolling_engine_e2e_two_algorithms_three_days(tmp_path: Path) -> None:
    data_path = tmp_path / "multi_day.csv"
    rows = []
    for day in range(1, 4):
        for hour in range(10):
            is_anomaly = hour >= 8
            rows.append({
                "timestamp": f"2024-02-0{day}T{hour:02d}:00:00Z",
                "value": 80.0 if is_anomaly else float(10 + hour % 3),
                "is_anomaly": 1 if is_anomaly else 0,
            })
    pd.DataFrame(rows).to_csv(data_path, index=False)

    store = SqliteTrackingStore(tmp_path / "tracking.db")
    result = run_rolling_experiment(
        data_path,
        algorithms=[AlgorithmConfig(name="three_sigma"), AlgorithmConfig(name="iqr")],
        policy=ExperimentPolicy(validate_ratio=0.7),
        store=store,
    )

    assert result.experiment.status == "completed"
    assert len(result.cycles) == 4
    assert len(result.ledger) == 40
    assert len(result.leaderboard) == 2
    assert result.leaderboard[0].mean_pa_f1 >= result.leaderboard[1].mean_pa_f1
    assert all(c.active_model_id is not None for c in result.cycles)
    assert all(row.active_model_id.endswith(("2024-02-01", "2024-02-02")) for row in result.ledger)

    experiments = store.list_rolling_experiments()
    assert experiments[0]["experiment_id"] == result.experiment.experiment_id
    assert store.count_rolling_predictions(result.experiment.experiment_id) == 40


def test_rolling_engine_e2e_with_synthetic_row_index(tmp_path: Path) -> None:
    data_path = tmp_path / "tsb_like.csv"
    rows = []
    for index in range(30):
        is_anomaly = index % 10 >= 8
        rows.append({
            "Data": 80.0 if is_anomaly else float(10 + index % 3),
            "Label": 1 if is_anomaly else 0,
        })
    pd.DataFrame(rows).to_csv(data_path, index=False)

    store = SqliteTrackingStore(tmp_path / "tracking.db")
    result = run_rolling_experiment(
        data_path,
        algorithms=[AlgorithmConfig(name="three_sigma")],
        policy=ExperimentPolicy(validate_ratio=0.7),
        synthetic_time=SyntheticTimeConfig(
            time_index_column="__row_index__",
            synthetic_start_time="2024-02-01T00:00:00Z",
            synthetic_interval="2h",
        ),
        store=store,
    )

    assert result.experiment.status == "completed"
    assert len(result.cycles) == 2
    assert len(result.ledger) == 18
    assert store.count_rolling_predictions(result.experiment.experiment_id) == 18
