from datetime import UTC, date, datetime

from nextaiops_algo.pipeline.rolling import (
    AlgorithmConfig,
    ExperimentPolicy,
    PredictionLedgerRow,
    RollingDayCycle,
    RollingExperiment,
    RollingExperimentResult,
    RollingLeaderboardRow,
)
from nextaiops_algo.pipeline.rolling_data import (
    DayPartition,
    ExclusionReason,
    PartitionStatus,
)
from nextaiops_algo.ui import app


def test_rolling_workbench_builds_partition_quality_table() -> None:
    partitions = [
        DayPartition(
            date=date(2024, 2, 1),
            row_count=10,
            has_label=True,
            label_coverage=1.0,
            status=PartitionStatus.VALID,
            exclusion_reason=None,
        ),
        DayPartition(
            date=date(2024, 2, 2),
            row_count=5,
            has_label=True,
            label_coverage=0.2,
            status=PartitionStatus.EXCLUDED,
            exclusion_reason=ExclusionReason.LOW_LABEL_COVERAGE,
        ),
    ]

    df = app._build_partition_dataframe(partitions)

    assert list(df["日期"]) == ["2024-02-01", "2024-02-02"]
    assert list(df["状态"]) == ["valid", "excluded"]
    assert df.loc[1, "排除原因"] == "LOW_LABEL_COVERAGE"
    assert len(app._rolling_valid_partitions(partitions)) == 1


def test_rolling_workbench_builds_result_tables() -> None:
    result = _sample_result()

    cycle_df = app._build_cycle_dataframe(result)
    leaderboard_df = app._build_leaderboard_dataframe(result)
    ledger_df = app._build_ledger_dataframe(result)
    timeline_df = app._build_active_timeline_dataframe(result)
    exclusion_df = app._build_exclusion_dataframe([], result)

    assert cycle_df.loc[0, "active_model_id"] == "three_sigma@D2024-02-01"
    assert cycle_df.loc[1, "状态"] == "partial_failed"
    assert leaderboard_df.loc[0, "Mean PA-F1"] == 0.8
    assert ledger_df.loc[0, "predicted_label"] == 1
    assert timeline_df.loc[0, "active_model_id"] == "three_sigma@D2024-02-01"
    assert exclusion_df.loc[0, "类型"] == "partial_failed"


def test_rolling_policy_signature_changes_when_policy_changes() -> None:
    base = app._rolling_policy_signature(
        data_source="demo.csv",
        date_column=None,
        selected_algorithms=["three_sigma"],
        algorithm_params={"three_sigma": {}},
        policy=ExperimentPolicy(validate_ratio=0.7),
    )
    changed = app._rolling_policy_signature(
        data_source="demo.csv",
        date_column=None,
        selected_algorithms=["three_sigma"],
        algorithm_params={"three_sigma": {}},
        policy=ExperimentPolicy(validate_ratio=0.8),
    )

    assert base != changed


def _sample_result() -> RollingExperimentResult:
    started = datetime(2024, 2, 1, tzinfo=UTC)
    ended = datetime(2024, 2, 2, tzinfo=UTC)
    config = AlgorithmConfig(name="three_sigma", params={})
    experiment = RollingExperiment(
        experiment_id="exp-1",
        dataset_path="demo.csv",
        date_column=None,
        algorithms=[config],
        policy=ExperimentPolicy(validate_ratio=0.7),
        status="partial_failed",
        created_at=started,
    )
    completed = RollingDayCycle(
        cutoff_day=date(2024, 2, 1),
        algorithm_name="three_sigma",
        params={},
        train_rows=7,
        validate_rows=3,
        active_interval_start=started,
        active_interval_end=ended,
        status="completed",
        metrics={"pa_f1": 0.8},
        active_model_id="three_sigma@D2024-02-01",
    )
    failed = RollingDayCycle(
        cutoff_day=date(2024, 2, 2),
        algorithm_name="iqr",
        params={},
        train_rows=10,
        validate_rows=4,
        active_interval_start=started,
        active_interval_end=ended,
        status="partial_failed",
        error_message="boom",
    )
    ledger = PredictionLedgerRow(
        timestamp=started,
        algorithm_name="three_sigma",
        params={},
        cutoff_day=date(2024, 2, 1),
        active_model_id="three_sigma@D2024-02-01",
        predicted_label=1,
        score=3.5,
        label=1,
    )
    leaderboard = RollingLeaderboardRow(
        algorithm_name="three_sigma",
        params={},
        mean_pa_f1=0.8,
        median_pa_f1=0.8,
        success_rate=1.0,
        cycles_completed=1,
        cycles_failed=0,
    )
    return RollingExperimentResult(
        experiment=experiment,
        cycles=[completed, failed],
        ledger=[ledger],
        leaderboard=[leaderboard],
        blocked_intervals=[],
    )
