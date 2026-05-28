"""Run rolling experiments across every file in a DatasetBundle."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from statistics import median
from typing import Literal

from pydantic import BaseModel, Field

from nextaiops_algo.pipeline.dataset_bundle import DatasetBundle
from nextaiops_algo.pipeline.rolling import (
    AlgorithmConfig,
    ExperimentPolicy,
    RollingExperimentResult,
    run_rolling_experiment,
)
from nextaiops_algo.pipeline.rolling_data import SyntheticTimeConfig

RollingBundleProgress = Callable[[int, int, str], None]
RollingBundleCellStatus = Literal["completed", "partial_failed", "failed"]


class RollingBundleCellResult(BaseModel):
    """Result for one file in a rolling bundle run."""

    file_name: str
    status: RollingBundleCellStatus
    result: RollingExperimentResult | None = None
    error_message: str | None = None


class RollingBundleResult(BaseModel):
    """Aggregated result for a multi-file rolling experiment."""

    bundle_id: str
    dataset_id: str
    file_names: list[str]
    algorithms: list[AlgorithmConfig]
    policy: ExperimentPolicy
    date_column: str | None
    synthetic_time: SyntheticTimeConfig | None
    cells: list[RollingBundleCellResult]
    algorithm_metrics: dict[str, dict[str, float]] = Field(default_factory=dict)


def run_rolling_bundle(
    bundle: DatasetBundle,
    algorithms: list[AlgorithmConfig],
    *,
    date_column: str | None = None,
    policy: ExperimentPolicy | None = None,
    synthetic_time: SyntheticTimeConfig | None = None,
    progress_callback: RollingBundleProgress | None = None,
) -> RollingBundleResult:
    """Run rolling experiment independently for each file in a DatasetBundle.

    Args:
        bundle: Loaded and schema-validated DatasetBundle.
        algorithms: Algorithm configurations to run.
        date_column: Optional date/timestamp column override.
        policy: Rolling execution policy (shared across all files).
        synthetic_time: Optional synthetic time config (shared across all files).
        progress_callback: Optional callback receiving current index, total count,
            and file name before each file starts.

    Returns:
        RollingBundleResult with cell-level results and aggregate metrics.
    """
    if not algorithms:
        raise ValueError("algorithms must not be empty")

    bundle_id = uuid.uuid4().hex[:12]
    resolved_policy = policy or ExperimentPolicy()
    cells: list[RollingBundleCellResult] = []
    total_files = bundle.file_count

    for file_index, dataset_file in enumerate(bundle.files, start=1):
        if progress_callback is not None:
            progress_callback(file_index, total_files, dataset_file.name)

        try:
            run_result = run_rolling_experiment(
                dataset_file.path,
                algorithms=algorithms,
                date_column=date_column,
                policy=resolved_policy,
                synthetic_time=synthetic_time,
            )
            cells.append(
                RollingBundleCellResult(
                    file_name=dataset_file.name,
                    status=_cell_status(run_result),
                    result=run_result,
                )
            )
        except Exception as exc:
            cells.append(
                RollingBundleCellResult(
                    file_name=dataset_file.name,
                    status="failed",
                    error_message=str(exc),
                )
            )

    algorithm_metrics = _aggregate_by_algorithm(algorithms, cells)

    return RollingBundleResult(
        bundle_id=bundle_id,
        dataset_id=bundle.dataset_id,
        file_names=[dataset_file.name for dataset_file in bundle.files],
        algorithms=algorithms,
        policy=resolved_policy,
        date_column=date_column,
        synthetic_time=synthetic_time,
        cells=cells,
        algorithm_metrics=algorithm_metrics,
    )


def _cell_status(result: RollingExperimentResult) -> RollingBundleCellStatus:
    """Derive cell status from rolling experiment result."""
    status = result.experiment.status
    if status == "completed":
        return "completed"
    if status == "partial_failed":
        return "partial_failed"
    return "failed"


def _aggregate_by_algorithm(
    algorithms: list[AlgorithmConfig],
    cells: list[RollingBundleCellResult],
) -> dict[str, dict[str, float]]:
    """Aggregate leaderboard metrics across all files for each algorithm."""
    aggregates: dict[str, dict[str, float]] = {}
    successful_cells = [cell for cell in cells if cell.result is not None]

    for algo in algorithms:
        algo_name = algo.name

        # Collect leaderboard rows for this algorithm across all files
        pa_f1_values: list[float] = []
        success_rates: list[float] = []
        total_cycles_completed = 0
        total_cycles_failed = 0

        for cell in successful_cells:
            assert cell.result is not None
            # Match by algorithm name only (params may be normalized differently)
            matching_rows = [
                row
                for row in cell.result.leaderboard
                if row.algorithm_name == algo_name
            ]
            for row in matching_rows:
                pa_f1_values.append(row.mean_pa_f1)
                success_rates.append(row.success_rate)
                total_cycles_completed += row.cycles_completed
                total_cycles_failed += row.cycles_failed

        if not pa_f1_values:
            aggregates[algo_name] = {
                "file_success_count": 0.0,
                "file_count": float(len(cells)),
                "success_rate": 0.0,
            }
            continue

        file_success_count = float(len([c for c in successful_cells if _has_algo(c, algo_name)]))
        aggregates[algo_name] = {
            "mean_pa_f1": sum(pa_f1_values) / len(pa_f1_values),
            "median_pa_f1": float(median(pa_f1_values)),
            "min_pa_f1": min(pa_f1_values),
            "max_pa_f1": max(pa_f1_values),
            "mean_success_rate": sum(success_rates) / len(success_rates),
            "total_cycles_completed": float(total_cycles_completed),
            "total_cycles_failed": float(total_cycles_failed),
            "file_success_count": file_success_count,
            "file_count": float(len(cells)),
            "success_rate": file_success_count / len(cells),
        }

    return aggregates


def _has_algo(cell: RollingBundleCellResult, algo_name: str) -> bool:
    """Check if cell has results for the given algorithm."""
    if cell.result is None:
        return False
    return any(row.algorithm_name == algo_name for row in cell.result.leaderboard)
