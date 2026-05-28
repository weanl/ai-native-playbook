"""Rolling experiment execution engine."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator

from nextaiops_algo.algorithms.base import AnomalyDetector
from nextaiops_algo.algorithms.params import format_experiment_label, identity_params
from nextaiops_algo.algorithms.registry import (
    create_algorithm,
    get_algorithm_param_specs,
    normalize_algorithm_params,
)
from nextaiops_algo.core.table import Table
from nextaiops_algo.pipeline.evaluate import evaluate
from nextaiops_algo.pipeline.preprocess import read_to_table
from nextaiops_algo.pipeline.rolling_data import (
    PartitionStatus,
    build_day_partitions,
    cumulative_training_window,
    partition_tables,
    split_train_validate,
)
from nextaiops_algo.pipeline.run import _validate_input, _validate_output
from nextaiops_algo.storage.sqlite_tracking import SqliteTrackingStore

RollingExperimentStatus = Literal["completed", "partial_failed", "failed"]
RollingDayCycleStatus = Literal["completed", "partial_failed", "blocked"]
AutoActivePolicy = Literal["latest"]
AlgorithmErrorPolicy = Literal["partial_failed"]


class AlgorithmConfig(BaseModel):
    """Configuration for one algorithm in a rolling experiment."""

    name: str
    params: dict[str, object] = Field(default_factory=dict)


class ExperimentPolicy(BaseModel):
    """Policy controlling rolling experiment execution."""

    cadence: Literal["1d"] = "1d"
    validate_ratio: float = 0.7
    label_coverage_threshold: float | None = None
    auto_active: AutoActivePolicy = "latest"
    on_algorithm_error: AlgorithmErrorPolicy = "partial_failed"

    @field_validator("validate_ratio")
    @classmethod
    def _validate_ratio(cls, value: float) -> float:
        if not 0 < value < 1:
            raise ValueError("validate_ratio must be in (0, 1)")
        return value

    @field_validator("label_coverage_threshold")
    @classmethod
    def _validate_threshold(cls, value: float | None) -> float | None:
        if value is not None and not 0 <= value <= 1:
            raise ValueError("label_coverage_threshold must be in [0, 1]")
        return value


class RollingExperiment(BaseModel):
    """Top-level rolling experiment metadata."""

    experiment_id: str
    dataset_path: str
    date_column: str | None
    algorithms: list[AlgorithmConfig]
    policy: ExperimentPolicy
    status: RollingExperimentStatus
    created_at: datetime


class RollingDayCycle(BaseModel):
    """Execution summary for one cutoff-day cycle."""

    cutoff_day: date
    algorithm_name: str
    params: dict[str, object]
    train_rows: int
    validate_rows: int
    active_interval_start: datetime | None
    active_interval_end: datetime | None
    status: RollingDayCycleStatus
    metrics: dict[str, float] = Field(default_factory=dict)
    active_model_id: str | None = None
    error_message: str | None = None
    exclusion_reason: str | None = None


class PredictionLedgerRow(BaseModel):
    """One active-interval prediction row."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    timestamp: Any
    algorithm_name: str
    params: dict[str, object]
    cutoff_day: date
    active_model_id: str
    predicted_label: int
    score: float | None
    label: int | None


class RollingLeaderboardRow(BaseModel):
    """Aggregated cross-day ranking row for one algorithm config."""

    algorithm_name: str
    params: dict[str, object]
    mean_pa_f1: float
    median_pa_f1: float
    success_rate: float
    cycles_completed: int
    cycles_failed: int


class RollingExperimentResult(BaseModel):
    """Result returned by ``run_rolling_experiment``."""

    experiment: RollingExperiment
    cycles: list[RollingDayCycle]
    ledger: list[PredictionLedgerRow]
    leaderboard: list[RollingLeaderboardRow]
    blocked_intervals: list[RollingDayCycle]


def run_rolling_experiment(
    dataset_path: str | Path,
    algorithms: list[AlgorithmConfig],
    *,
    date_column: str | None = None,
    policy: ExperimentPolicy | None = None,
    store: SqliteTrackingStore | None = None,
) -> RollingExperimentResult:
    """Run an offline rolling experiment over day partitions.

    Args:
        dataset_path: Path or builtin dataset name readable by existing loaders.
        algorithms: Algorithm configurations to run.
        date_column: Optional date/timestamp column override.
        policy: Rolling execution policy.
        store: Optional tracking store. Defaults to ``SqliteTrackingStore``.

    Returns:
        Rolling experiment result with cycles, ledger, and leaderboard.
    """
    if not algorithms:
        raise ValueError("algorithms must not be empty")

    resolved_policy = policy or ExperimentPolicy()
    tracking_store = store or SqliteTrackingStore()
    created_at = datetime.now()
    experiment_id = uuid.uuid4().hex[:12]
    source_table = read_to_table(dataset_path)

    partitions = build_day_partitions(
        source_table,
        date_column=date_column,
        threshold=resolved_policy.label_coverage_threshold,
    )
    partitioned = partition_tables(source_table, partitions, date_column=date_column)
    valid_days = sorted(
        p.date.isoformat()
        for p in partitions
        if p.status == PartitionStatus.VALID and p.date.isoformat() in partitioned
    )

    cycles: list[RollingDayCycle] = []
    ledger: list[PredictionLedgerRow] = []
    blocked_intervals: list[RollingDayCycle] = []

    for index, cutoff_day in enumerate(valid_days[:-1]):
        next_day = valid_days[index + 1]
        active_table = partitioned[next_day]
        active_start, active_end = _table_time_bounds(active_table)
        train_window = cumulative_training_window(partitioned, cutoff_day)

        try:
            train_table, validate_table = split_train_validate(
                train_window,
                resolved_policy.validate_ratio,
            )
        except Exception as exc:
            for config in algorithms:
                blocked = RollingDayCycle(
                    cutoff_day=date.fromisoformat(cutoff_day),
                    algorithm_name=config.name,
                    params=dict(config.params),
                    train_rows=len(train_window.df),
                    validate_rows=0,
                    active_interval_start=active_start,
                    active_interval_end=active_end,
                    status="blocked",
                    error_message=str(exc),
                    exclusion_reason="split_failed",
                )
                cycles.append(blocked)
                blocked_intervals.append(blocked)
            continue

        for config in algorithms:
            cycle, active_output = _run_algorithm_cycle(
                config=config,
                cutoff_day=cutoff_day,
                train_table=train_table,
                validate_table=validate_table,
                active_table=active_table,
                active_start=active_start,
                active_end=active_end,
            )
            cycles.append(cycle)
            if cycle.status == "completed" and cycle.active_model_id is not None and active_output is not None:
                ledger.extend(_build_ledger_rows(
                    active_table=active_table,
                    output_table=active_output,
                    config=config,
                    cutoff_day=date.fromisoformat(cutoff_day),
                    active_model_id=cycle.active_model_id,
                ))
            elif cycle.status == "blocked":
                blocked_intervals.append(cycle)

    experiment = RollingExperiment(
        experiment_id=experiment_id,
        dataset_path=str(dataset_path),
        date_column=date_column,
        algorithms=algorithms,
        policy=resolved_policy,
        status=_experiment_status(cycles),
        created_at=created_at,
    )
    leaderboard = _build_leaderboard(cycles)
    result = RollingExperimentResult(
        experiment=experiment,
        cycles=cycles,
        ledger=ledger,
        leaderboard=leaderboard,
        blocked_intervals=blocked_intervals,
    )
    tracking_store.log_rolling_experiment(result)
    return result


def _run_algorithm_cycle(
    *,
    config: AlgorithmConfig,
    cutoff_day: str,
    train_table: Table,
    validate_table: Table,
    active_table: Table,
    active_start: datetime | None,
    active_end: datetime | None,
) -> tuple[RollingDayCycle, Table | None]:
    params = normalize_algorithm_params(config.name, config.params)
    specs = get_algorithm_param_specs(config.name)
    run_identity_params = identity_params(specs, params) if specs else params
    model_id = f"{format_experiment_label(config.name, run_identity_params)}@D{cutoff_day}"

    try:
        algo_base = create_algorithm(config.name, params)
        if algo_base is None:
            raise ValueError(f"Algorithm '{config.name}' not found in registry")
        algo: AnomalyDetector = algo_base  # type: ignore[assignment]
        _validate_input(train_table, algo)
        algo.fit(train_table)

        validate_output = algo.detect(validate_table)
        _validate_output(validate_table, validate_output, algo)
        metrics = evaluate(validate_table, validate_output)

        active_output = algo.detect(active_table)
        _validate_output(active_table, active_output, algo)

        return RollingDayCycle(
            cutoff_day=date.fromisoformat(cutoff_day),
            algorithm_name=config.name,
            params=params,
            train_rows=len(train_table.df),
            validate_rows=len(validate_table.df),
            active_interval_start=active_start,
            active_interval_end=active_end,
            status="completed",
            metrics=metrics,
            active_model_id=model_id,
        ), active_output
    except Exception as exc:
        return RollingDayCycle(
            cutoff_day=date.fromisoformat(cutoff_day),
            algorithm_name=config.name,
            params=params,
            train_rows=len(train_table.df),
            validate_rows=len(validate_table.df),
            active_interval_start=active_start,
            active_interval_end=active_end,
            status="partial_failed",
            error_message=str(exc),
        ), None


def _build_ledger_rows(
    *,
    active_table: Table,
    output_table: Table,
    config: AlgorithmConfig,
    cutoff_day: date,
    active_model_id: str,
) -> list[PredictionLedgerRow]:
    timestamps = output_table.timestamps()
    labels = active_table.labels()
    score_values = _max_score(output_table)
    rows: list[PredictionLedgerRow] = []

    for pos, (_, output_row) in enumerate(output_table.df.iterrows()):
        timestamp = timestamps.iloc[pos] if timestamps is not None else pos
        label = None if labels is None else int(labels.iloc[pos])
        score = None if score_values is None else float(score_values.iloc[pos])
        rows.append(PredictionLedgerRow(
            timestamp=timestamp,
            algorithm_name=config.name,
            params=dict(config.params),
            cutoff_day=cutoff_day,
            active_model_id=active_model_id,
            predicted_label=int(output_row["predicted_label"]),
            score=score,
            label=label,
        ))
    return rows


def _max_score(output_table: Table) -> pd.Series | None:
    score_cols = [col for col in output_table.df.columns if col.endswith(".anomaly_score")]
    if not score_cols:
        return None
    return output_table.df[score_cols].max(axis=1)


def _table_time_bounds(table: Table) -> tuple[datetime | None, datetime | None]:
    ts = table.timestamps()
    if ts is None or ts.empty:
        return None, None
    parsed = pd.to_datetime(ts, utc=True)
    start = parsed.min().to_pydatetime()
    end = parsed.max().to_pydatetime()
    return start, end


def _build_leaderboard(cycles: list[RollingDayCycle]) -> list[RollingLeaderboardRow]:
    grouped: dict[tuple[str, str], list[RollingDayCycle]] = {}
    for cycle in cycles:
        key = (cycle.algorithm_name, repr(sorted(cycle.params.items())))
        grouped.setdefault(key, []).append(cycle)

    rows: list[RollingLeaderboardRow] = []
    for cycle_group in grouped.values():
        first = cycle_group[0]
        completed = [cycle for cycle in cycle_group if cycle.status == "completed"]
        failed = [cycle for cycle in cycle_group if cycle.status != "completed"]
        pa_f1_values = [cycle.metrics["pa_f1"] for cycle in completed if "pa_f1" in cycle.metrics]
        mean_pa_f1 = float(sum(pa_f1_values) / len(pa_f1_values)) if pa_f1_values else 0.0
        median_pa_f1 = float(pd.Series(pa_f1_values).median()) if pa_f1_values else 0.0
        denominator = len(completed) + len(failed)
        success_rate = float(len(completed) / denominator) if denominator else 0.0
        rows.append(RollingLeaderboardRow(
            algorithm_name=first.algorithm_name,
            params=dict(first.params),
            mean_pa_f1=mean_pa_f1,
            median_pa_f1=median_pa_f1,
            success_rate=success_rate,
            cycles_completed=len(completed),
            cycles_failed=len(failed),
        ))

    return sorted(
        rows,
        key=lambda row: (row.mean_pa_f1, row.median_pa_f1, row.success_rate),
        reverse=True,
    )


def _experiment_status(cycles: list[RollingDayCycle]) -> RollingExperimentStatus:
    if not cycles or all(cycle.status != "completed" for cycle in cycles):
        return "failed"
    if any(cycle.status != "completed" for cycle in cycles):
        return "partial_failed"
    return "completed"
