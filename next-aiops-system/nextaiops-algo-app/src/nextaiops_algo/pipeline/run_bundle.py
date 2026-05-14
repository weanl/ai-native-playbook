"""Run a single algorithm across every file in a DatasetBundle."""

import json
import uuid
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from nextaiops_algo.core.experiment import RunResult
from nextaiops_algo.pipeline.dataset_bundle import DatasetBundle
from nextaiops_algo.pipeline.run import run_experiment


class BundleFileResult(BaseModel):
    """Experiment result for one file within a DatasetBundle."""

    file_name: str
    run_result: RunResult


class BundleRunResult(BaseModel):
    """Aggregated result for one algorithm run over a DatasetBundle."""

    bundle_id: str
    dataset_id: str
    algorithm_name: str
    file_results: list[BundleFileResult]
    metrics: dict[str, float]
    artifacts_path: str


def run_bundle_experiment(
    bundle: DatasetBundle,
    algorithm_name: str,
    params: dict[str, object] | None = None,
    output_dir: Path | None = None,
    split_ratio: float = 0.7,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> BundleRunResult:
    """Run one algorithm independently for each file in a DatasetBundle.

    Args:
        bundle: Loaded and schema-validated DatasetBundle.
        algorithm_name: Name of algorithm (must be in REGISTRY).
        params: Algorithm parameters passed through to each file run.
        output_dir: Base directory for artifacts. If None, uses default.
        split_ratio: Fraction for training data.
        progress_callback: Optional callback receiving current index, total count,
            and file name before each file run starts.

    Returns:
        BundleRunResult with per-file results and mean metrics.
    """
    bundle_id = uuid.uuid4().hex[:12]
    file_results: list[BundleFileResult] = []

    total_files = len(bundle.files)
    for index, dataset_file in enumerate(bundle.files, start=1):
        if progress_callback is not None:
            progress_callback(index, total_files, dataset_file.name)
        result = run_experiment(
            dataset_path=dataset_file.path,
            algorithm_name=algorithm_name,
            params=params,
            output_dir=output_dir,
            split_ratio=split_ratio,
        )
        file_results.append(BundleFileResult(file_name=dataset_file.name, run_result=result))

    metrics = _mean_metrics([file_result.run_result.metrics for file_result in file_results])
    artifacts_path = _write_bundle_summary(
        bundle_id=bundle_id,
        bundle=bundle,
        algorithm_name=algorithm_name,
        file_results=file_results,
        metrics=metrics,
        output_dir=output_dir,
    )

    return BundleRunResult(
        bundle_id=bundle_id,
        dataset_id=bundle.dataset_id,
        algorithm_name=algorithm_name,
        file_results=file_results,
        metrics=metrics,
        artifacts_path=str(artifacts_path),
    )


def _mean_metrics(metric_sets: list[dict[str, float]]) -> dict[str, float]:
    metric_names = sorted({name for metrics in metric_sets for name in metrics})
    mean_metrics = {
        name: sum(metrics.get(name, 0.0) for metrics in metric_sets) / len(metric_sets)
        for name in metric_names
    }
    mean_metrics["file_count"] = float(len(metric_sets))
    return mean_metrics


def _write_bundle_summary(
    bundle_id: str,
    bundle: DatasetBundle,
    algorithm_name: str,
    file_results: list[BundleFileResult],
    metrics: dict[str, float],
    output_dir: Path | None,
) -> Path:
    base_dir = output_dir if output_dir is not None else Path.home() / ".nextaiops_algo" / "runs"
    artifacts_path = base_dir / f"bundle_{bundle_id}"
    artifacts_path.mkdir(parents=True, exist_ok=True)

    summary = {
        "bundle_id": bundle_id,
        "dataset_id": bundle.dataset_id,
        "algorithm_name": algorithm_name,
        "file_count": bundle.file_count,
        "metrics": metrics,
        "files": [
            {
                "file_name": file_result.file_name,
                "run_id": file_result.run_result.run_id,
                "metrics": file_result.run_result.metrics,
                "artifacts_path": file_result.run_result.artifacts_path,
            }
            for file_result in file_results
        ],
    }
    (artifacts_path / "bundle_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return artifacts_path
