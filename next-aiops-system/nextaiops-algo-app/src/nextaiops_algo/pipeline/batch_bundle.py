"""Run multiple algorithms across every file in a DatasetBundle."""

import json
import uuid
from collections import defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path
from statistics import median
from typing import Literal

from pydantic import BaseModel

from nextaiops_algo.algorithms.registry import REGISTRY
from nextaiops_algo.core.experiment import BatchStatus, RunResult, RunStatus
from nextaiops_algo.pipeline.dataset_bundle import DatasetBundle
from nextaiops_algo.pipeline.run import run_experiment

BatchBundleProgress = Callable[[int, int, str, str], None]


class BatchBundleCellResult(BaseModel):
    """Result for one algorithm × file cell in a batch bundle run."""

    algorithm_name: str
    file_name: str
    status: RunStatus
    run_result: RunResult | None = None
    error_message: str | None = None


class BatchBundleResult(BaseModel):
    """Aggregated result for a multi-algorithm DatasetBundle experiment."""

    batch_bundle_id: str
    dataset_id: str
    algorithm_names: list[str]
    file_names: list[str]
    cells: list[BatchBundleCellResult]
    status: BatchStatus
    algorithm_metrics: dict[str, dict[str, float]]
    file_metrics: dict[str, dict[str, float]]
    artifacts_path: str


def run_batch_bundle(
    bundle: DatasetBundle,
    algorithms: Sequence[str] | Literal["__all__"],
    params_override: dict[str, dict[str, object]] | None = None,
    output_dir: Path | None = None,
    split_ratio: float = 0.7,
    progress_callback: BatchBundleProgress | None = None,
) -> BatchBundleResult:
    """Run multiple algorithms independently for each file in a DatasetBundle.

    Args:
        bundle: Loaded and schema-validated DatasetBundle.
        algorithms: Algorithm names, or "__all__" for all registered algorithms.
        params_override: Per-algorithm parameter overrides.
        output_dir: Base directory for artifacts. If None, uses default.
        split_ratio: Fraction for training data.
        progress_callback: Optional callback receiving current index, total count,
            algorithm name, and file name before each cell starts.

    Returns:
        BatchBundleResult with cell-level results and aggregate metrics.
    """
    algorithm_names = sorted(REGISTRY.keys()) if algorithms == "__all__" else list(algorithms)
    batch_bundle_id = uuid.uuid4().hex[:12]
    cells: list[BatchBundleCellResult] = []
    total_cells = len(algorithm_names) * bundle.file_count

    for algo_index, algorithm_name in enumerate(algorithm_names):
        algo_params = params_override.get(algorithm_name, {}) if params_override else {}

        for file_index, dataset_file in enumerate(bundle.files, start=1):
            cell_index = algo_index * bundle.file_count + file_index
            if progress_callback is not None:
                progress_callback(cell_index, total_cells, algorithm_name, dataset_file.name)

            if algorithm_name not in REGISTRY:
                cells.append(
                    BatchBundleCellResult(
                        algorithm_name=algorithm_name,
                        file_name=dataset_file.name,
                        status=RunStatus.FAILED,
                        error_message=f"Algorithm not found in REGISTRY: {algorithm_name}",
                    )
                )
                continue

            try:
                run_result = run_experiment(
                    dataset_path=dataset_file.path,
                    algorithm_name=algorithm_name,
                    params=algo_params,
                    output_dir=output_dir,
                    split_ratio=split_ratio,
                )
                cells.append(
                    BatchBundleCellResult(
                        algorithm_name=algorithm_name,
                        file_name=dataset_file.name,
                        status=RunStatus.COMPLETED,
                        run_result=run_result,
                    )
                )
            except Exception as exc:
                cells.append(
                    BatchBundleCellResult(
                        algorithm_name=algorithm_name,
                        file_name=dataset_file.name,
                        status=RunStatus.FAILED,
                        error_message=str(exc),
                    )
                )

    algorithm_metrics = _aggregate_by_algorithm(algorithm_names, cells, bundle.file_count)
    file_metrics = _aggregate_by_file([dataset_file.name for dataset_file in bundle.files], cells)
    status = _overall_status(cells)
    artifacts_path = _write_batch_bundle_summary(
        batch_bundle_id=batch_bundle_id,
        bundle=bundle,
        algorithm_names=algorithm_names,
        cells=cells,
        status=status,
        algorithm_metrics=algorithm_metrics,
        file_metrics=file_metrics,
        output_dir=output_dir,
    )

    return BatchBundleResult(
        batch_bundle_id=batch_bundle_id,
        dataset_id=bundle.dataset_id,
        algorithm_names=algorithm_names,
        file_names=[dataset_file.name for dataset_file in bundle.files],
        cells=cells,
        status=status,
        algorithm_metrics=algorithm_metrics,
        file_metrics=file_metrics,
        artifacts_path=str(artifacts_path),
    )


def _aggregate_by_algorithm(
    algorithm_names: Sequence[str],
    cells: Sequence[BatchBundleCellResult],
    file_count: int,
) -> dict[str, dict[str, float]]:
    by_algorithm: dict[str, list[BatchBundleCellResult]] = defaultdict(list)
    for cell in cells:
        by_algorithm[cell.algorithm_name].append(cell)

    aggregates: dict[str, dict[str, float]] = {}
    for algorithm_name in algorithm_names:
        algo_cells = by_algorithm.get(algorithm_name, [])
        successful_metrics = [
            cell.run_result.metrics
            for cell in algo_cells
            if cell.status == RunStatus.COMPLETED and cell.run_result is not None
        ]
        aggregates[algorithm_name] = _aggregate_metric_sets(successful_metrics)
        aggregates[algorithm_name]["success_rate"] = (
            len(successful_metrics) / file_count if file_count > 0 else 0.0
        )
        aggregates[algorithm_name]["file_count"] = float(file_count)
        aggregates[algorithm_name]["success_count"] = float(len(successful_metrics))
    return aggregates


def _aggregate_by_file(
    file_names: Sequence[str],
    cells: Sequence[BatchBundleCellResult],
) -> dict[str, dict[str, float]]:
    by_file: dict[str, list[BatchBundleCellResult]] = defaultdict(list)
    for cell in cells:
        by_file[cell.file_name].append(cell)

    aggregates: dict[str, dict[str, float]] = {}
    for file_name in file_names:
        file_cells = by_file.get(file_name, [])
        successful_metrics = [
            cell.run_result.metrics
            for cell in file_cells
            if cell.status == RunStatus.COMPLETED and cell.run_result is not None
        ]
        aggregates[file_name] = _aggregate_metric_sets(successful_metrics)
        aggregates[file_name]["success_count"] = float(len(successful_metrics))
        aggregates[file_name]["algorithm_count"] = float(len(file_cells))
    return aggregates


def _aggregate_metric_sets(metric_sets: Sequence[dict[str, float]]) -> dict[str, float]:
    if not metric_sets:
        return {}

    metric_names = sorted({name for metrics in metric_sets for name in metrics})
    aggregates: dict[str, float] = {}
    for metric_name in metric_names:
        values = [metrics[metric_name] for metrics in metric_sets if metric_name in metrics]
        if not values:
            continue
        aggregates[f"mean_{metric_name}"] = sum(values) / len(values)
        aggregates[f"median_{metric_name}"] = float(median(values))
        aggregates[f"min_{metric_name}"] = min(values)
        aggregates[f"max_{metric_name}"] = max(values)
    return aggregates


def _overall_status(cells: Sequence[BatchBundleCellResult]) -> BatchStatus:
    completed = sum(1 for cell in cells if cell.status == RunStatus.COMPLETED)
    failed = sum(1 for cell in cells if cell.status == RunStatus.FAILED)
    if failed == 0:
        return BatchStatus.COMPLETED
    if completed > 0:
        return BatchStatus.PARTIAL_FAILED
    return BatchStatus.FAILED


def _write_batch_bundle_summary(
    batch_bundle_id: str,
    bundle: DatasetBundle,
    algorithm_names: Sequence[str],
    cells: Sequence[BatchBundleCellResult],
    status: BatchStatus,
    algorithm_metrics: dict[str, dict[str, float]],
    file_metrics: dict[str, dict[str, float]],
    output_dir: Path | None,
) -> Path:
    base_dir = output_dir if output_dir is not None else Path.home() / ".nextaiops_algo" / "runs"
    artifacts_path = base_dir / f"batch_bundle_{batch_bundle_id}"
    artifacts_path.mkdir(parents=True, exist_ok=True)

    summary = {
        "batch_bundle_id": batch_bundle_id,
        "dataset_id": bundle.dataset_id,
        "file_count": bundle.file_count,
        "algorithm_names": list(algorithm_names),
        "file_names": [dataset_file.name for dataset_file in bundle.files],
        "status": status.value,
        "algorithm_metrics": algorithm_metrics,
        "file_metrics": file_metrics,
        "cells": [
            {
                "algorithm_name": cell.algorithm_name,
                "file_name": cell.file_name,
                "status": cell.status.value,
                "run_id": cell.run_result.run_id if cell.run_result is not None else None,
                "metrics": cell.run_result.metrics if cell.run_result is not None else {},
                "artifacts_path": (
                    cell.run_result.artifacts_path if cell.run_result is not None else ""
                ),
                "error_message": cell.error_message,
            }
            for cell in cells
        ],
    }
    (artifacts_path / "batch_bundle_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return artifacts_path
