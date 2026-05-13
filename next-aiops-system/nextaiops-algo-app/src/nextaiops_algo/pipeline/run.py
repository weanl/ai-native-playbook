"""Main experiment orchestration - run_experiment entry point."""

import uuid
from datetime import datetime
from pathlib import Path

from nextaiops_algo.algorithms.base import AnomalyDetector
from nextaiops_algo.algorithms.params import format_experiment_label, identity_params
from nextaiops_algo.algorithms.registry import (
    create_algorithm,
    get_algorithm_param_specs,
    normalize_algorithm_params,
)
from nextaiops_algo.core.algorithm import Algorithm
from nextaiops_algo.core.exceptions import SchemaValidationError
from nextaiops_algo.core.experiment import ExperimentRun, RunResult, RunStatus
from nextaiops_algo.core.table import FieldRole, Table
from nextaiops_algo.storage.fs_artifact import FsArtifactStore
from nextaiops_algo.storage.sqlite_tracking import SqliteTrackingStore

from .evaluate import evaluate
from .preprocess import read_to_table, split_by_time


def _validate_input(table: Table, algo: Algorithm) -> None:
    """Validate that input Table meets algorithm's required roles.

    Args:
        table: Input Table to validate.
        algo: Algorithm that will process the Table.

    Raises:
        SchemaValidationError: If required roles are missing.
    """
    present_roles = set(table.schema.roles.values())
    missing = algo.required_input_roles - present_roles

    if missing:
        missing_str = ", ".join(r.value for r in missing)
        present_str = ", ".join(r.value for r in present_roles)
        raise SchemaValidationError(
            f"Algorithm '{algo.name}' requires roles [{missing_str}], "
            f"input only provides [{present_str}]",
            context={"algorithm": algo.name, "missing_roles": [r.value for r in missing]},
        )


def _validate_output(input_table: Table, result: Table, algo: Algorithm) -> None:
    """Validate that output Table meets AnomalyDetector contract.

    Checks:
    - predicted_label column exists with LABEL role
    - Output row count matches input
    - If input has timestamp, output must have same timestamp

    Args:
        input_table: Original input Table.
        result: Algorithm output Table.
        algo: Algorithm that produced the output.

    Raises:
        SchemaValidationError: If output contract is violated.
    """
    # Check predicted_label column
    if "predicted_label" not in result.df.columns:
        raise SchemaValidationError(
            f"Algorithm '{algo.name}' output missing required 'predicted_label' column",
            context={"algorithm": algo.name, "output_columns": list(result.df.columns)},
        )

    if result.schema.roles.get("predicted_label") != FieldRole.LABEL:
        raise SchemaValidationError(
            f"'predicted_label' column must have role LABEL, "
            f"found {result.schema.roles.get('predicted_label')}",
            context={"algorithm": algo.name},
        )

    # Check row count alignment
    if len(result.df) != len(input_table.df):
        raise SchemaValidationError(
            f"Output row count ({len(result.df)}) != input row count ({len(input_table.df)})",
            context={
                "algorithm": algo.name,
                "input_rows": len(input_table.df),
                "output_rows": len(result.df),
            },
        )

    # Check timestamp alignment if input has it
    input_ts = input_table.timestamps()
    if input_ts is not None:
        output_ts = result.timestamps()
        if output_ts is None:
            raise SchemaValidationError(
                "Input has timestamp column, but output does not",
                context={"algorithm": algo.name},
            )

        # Compare values (reset index to ignore index differences)
        input_ts_reset = input_ts.reset_index(drop=True)
        output_ts_reset = output_ts.reset_index(drop=True)

        if not input_ts_reset.equals(output_ts_reset):
            raise SchemaValidationError(
                "Output timestamp values do not match input timestamp values",
                context={"algorithm": algo.name},
            )


def run_experiment(
    dataset_path: str | Path,
    algorithm_name: str,
    params: dict[str, object] | None = None,
    output_dir: Path | None = None,
    split_ratio: float = 0.7,
) -> RunResult:
    """Run a complete experiment: load data, train, evaluate, persist.

    Flow:
    1. read_to_table → validate input
    2. split_by_time → train/test
    3. algo.fit(train) → algo.detect(test) → validate output
    4. evaluate → metrics
    5. log to SQLite + save artifacts
    6. generate viz.html
    7. return RunResult

    Args:
        dataset_path: Path to input data file (.csv/.out/.npy/.npz) or builtin dataset name.
        algorithm_name: Name of algorithm (must be in REGISTRY).
        params: Algorithm parameters (passed to algorithm if needed).
        output_dir: Base directory for artifacts. If None, uses default.
        split_ratio: Fraction for training data (0.0-1.0).

    Returns:
        RunResult with run_id, metrics, and artifacts_path.

    Raises:
        SchemaValidationError: If input/output schema validation fails.
        ValueError: If algorithm not found or invalid split_ratio.
    """
    normalized_params = normalize_algorithm_params(algorithm_name, params)

    # Create algorithm from registry for this run.
    algo_base = create_algorithm(algorithm_name, normalized_params)
    if algo_base is None:
        raise ValueError(f"Algorithm '{algorithm_name}' not found in registry")

    # Cast to AnomalyDetector (M0 only supports anomaly detection)
    algo: AnomalyDetector = algo_base  # type: ignore[assignment]

    # Initialize storage
    tracking_store = SqliteTrackingStore()
    artifact_store = FsArtifactStore(base_path=output_dir)

    # Generate run_id
    run_id = uuid.uuid4().hex[:12]

    # Step 1: Load and validate input (supports CSV, .out, npy, npz, builtin)
    full_table = read_to_table(dataset_path)
    _validate_input(full_table, algo)

    # Step 2: Split train/test
    train_table, test_table = split_by_time(full_table, ratio=split_ratio)

    # Step 3: Fit and detect
    algo.fit(train_table)
    result_table = algo.detect(test_table)

    # Validate output
    _validate_output(test_table, result_table, algo)

    # Step 4: Evaluate
    metrics = evaluate(test_table, result_table)

    # Step 5: Log run to tracking store
    artifacts_path = str(artifact_store.path_for(run_id, ""))
    run_record = ExperimentRun(
        run_id=run_id,
        dataset_version=Path(dataset_path).name,
        algorithm_name=algorithm_name,
        params=normalized_params,
        status=RunStatus.COMPLETED,
        artifacts_path=artifacts_path,
        created_at=datetime.now(),
    )
    tracking_store.log_run(run_record)

    # Log metrics
    for metric_name, metric_value in metrics.items():
        tracking_store.log_metric(run_id, metric_name, metric_value)

    # Step 6: Save artifacts (detect_output.csv + viz.html)
    # Persist detect output for batch overlay visualization
    detect_csv_path = Path(artifacts_path) / "detect_output.csv"
    detect_csv_path.parent.mkdir(parents=True, exist_ok=True)
    result_table.df.to_csv(detect_csv_path, index=False)

    specs = get_algorithm_param_specs(algorithm_name)
    run_identity_params = identity_params(specs, normalized_params) if specs else normalized_params
    experiment_label = format_experiment_label(algorithm_name, run_identity_params)
    (Path(artifacts_path) / "experiment_label.txt").write_text(experiment_label)

    # Import viz here to avoid circular import and handle missing plotly
    try:
        from nextaiops_algo.viz.timeseries import plot_timeseries

        viz_path = artifact_store.path_for(run_id, "viz.html")
        viz_html = plot_timeseries(result_table, viz_path)
        artifact_store.put(run_id, "viz.html", viz_html.encode("utf-8"))
    except ImportError:
        # plotly not installed - skip viz (env issue, not code)
        pass

    # Step 7: Return result
    return RunResult(
        run_id=run_id,
        metrics=metrics,
        artifacts_path=artifacts_path,
    )
