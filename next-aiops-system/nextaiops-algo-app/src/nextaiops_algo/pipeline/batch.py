"""Batch experiment engine - run multiple algorithms on a single dataset."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal

from nextaiops_algo.algorithms.registry import REGISTRY
from nextaiops_algo.core.experiment import BatchRun, BatchStatus, ExperimentRun, RunStatus
from nextaiops_algo.pipeline.run import run_experiment


def run_batch(
    dataset: str | Path,
    algorithms: list[str] | Literal["__all__"],
    params_override: dict[str, dict[str, object]] | None = None,
    output_dir: Path | None = None,
    split_ratio: float = 0.7,
) -> BatchRun:
    """Run multiple algorithms on a single dataset in sequence.

    Each algorithm is run independently. A single algorithm failure does not
    block the rest of the batch — the failed run is marked FAILED and
    execution continues.

    Args:
        dataset: Path to input data or builtin dataset name.
        algorithms: List of algorithm names, or "__all__" for all registered.
        params_override: Per-algorithm param overrides, keyed by algorithm name.
        output_dir: Base directory for artifacts. If None, uses default.
        split_ratio: Fraction for training data.

    Returns:
        BatchRun with status and per-algorithm ExperimentRun records.
    """
    # Resolve algorithm list
    algo_names = sorted(REGISTRY.keys()) if algorithms == "__all__" else list(algorithms)

    batch_id = uuid.uuid4().hex[:12]
    created_at = datetime.now()
    runs: list[ExperimentRun] = []

    n_total = len(algo_names)
    n_completed = 0
    n_failed = 0

    for idx, algo_name in enumerate(algo_names, start=1):
        print(f"[{idx}/{n_total}] Running {algo_name}...")

        # Check if algorithm is registered
        if algo_name not in REGISTRY:
            n_failed += 1
            runs.append(ExperimentRun(
                run_id=uuid.uuid4().hex[:12],
                dataset_version=Path(dataset).name if isinstance(dataset, Path) else str(dataset),
                algorithm_name=algo_name,
                params=params_override.get(algo_name, {}) if params_override else {},
                status=RunStatus.FAILED,
                artifacts_path="",
                created_at=datetime.now(),
            ))
            print(f"[{idx}/{n_total}] {algo_name} FAILED — not found in REGISTRY")
            continue

        # Get per-algorithm params
        algo_params: dict[str, object] = {}
        if params_override and algo_name in params_override:
            algo_params = params_override[algo_name]

        try:
            result = run_experiment(
                dataset_path=dataset,
                algorithm_name=algo_name,
                params=algo_params,
                output_dir=output_dir,
                split_ratio=split_ratio,
            )
            # Fetch the run record from tracking store to get ExperimentRun
            from nextaiops_algo.storage.sqlite_tracking import SqliteTrackingStore

            store = SqliteTrackingStore()
            stored_run = store.get_run(result.run_id)
            if stored_run is not None:
                runs.append(stored_run)
                n_completed += 1
            else:
                # Fallback: construct from result
                runs.append(ExperimentRun(
                    run_id=result.run_id,
                    dataset_version=Path(dataset).name if isinstance(dataset, Path) else str(dataset),
                    algorithm_name=algo_name,
                    params=algo_params,
                    status=RunStatus.COMPLETED,
                    artifacts_path=result.artifacts_path,
                    created_at=created_at,
                ))
                n_completed += 1

            print(f"[{idx}/{n_total}] {algo_name} COMPLETED")

        except Exception as e:
            n_failed += 1
            runs.append(ExperimentRun(
                run_id=uuid.uuid4().hex[:12],
                dataset_version=Path(dataset).name if isinstance(dataset, Path) else str(dataset),
                algorithm_name=algo_name,
                params=algo_params,
                status=RunStatus.FAILED,
                artifacts_path="",
                created_at=datetime.now(),
            ))
            print(f"[{idx}/{n_total}] {algo_name} FAILED — {e}")

    # Determine overall batch status
    if n_failed == 0:
        status = BatchStatus.COMPLETED
    elif n_completed > 0:
        status = BatchStatus.PARTIAL_FAILED
    else:
        status = BatchStatus.FAILED

    batch = BatchRun(
        batch_id=batch_id,
        dataset_source=str(dataset),
        algorithm_names=algo_names,
        created_at=created_at,
        runs=runs,
        status=status,
    )

    # Persist batch to tracking store
    from nextaiops_algo.storage.sqlite_tracking import SqliteTrackingStore

    store = SqliteTrackingStore()
    store.log_batch(batch)

    return batch
