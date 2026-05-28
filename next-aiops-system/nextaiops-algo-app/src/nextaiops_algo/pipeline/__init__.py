"""Pipeline module - Experiment orchestration layer.

This module provides the orchestration layer for NextAIOpsAlgoApp:
- preprocess: CSV → Table conversion + time-series split
- run: run_experiment main entry point
- batch: run_batch for multi-algorithm experiments
- batch_bundle: run_batch_bundle for multi-algorithm DatasetBundle experiments
- dataset_bundle: multi-file dataset loading with schema consistency checks
- evaluate: Metrics calculation (precision/recall/F1)

Pipeline does not directly import algorithm implementations;
it accesses algorithms via algorithms.registry.REGISTRY only.
"""

from .batch import run_batch
from .batch_bundle import BatchBundleResult, run_batch_bundle
from .dataset_bundle import DatasetBundle, DatasetFile, load_dataset_bundle
from .evaluate import evaluate
from .preprocess import (
    read_csv_to_table,
    read_dataset_bundle_from_zip,
    read_to_table,
    split_by_time,
)
from .rolling import (
    AlgorithmConfig,
    ExperimentPolicy,
    PredictionLedgerRow,
    RollingDayCycle,
    RollingExperiment,
    RollingExperimentResult,
    RollingLeaderboardRow,
    run_rolling_experiment,
)
from .rolling_data import (
    DayPartition,
    ExclusionReason,
    PartitionStatus,
    SyntheticTimeConfig,
    build_day_partitions,
    cumulative_training_window,
    partition_tables,
    split_train_validate,
)
from .run import run_experiment
from .run_bundle import BundleRunResult, run_bundle_experiment

__all__ = [
    "BundleRunResult",
    "BatchBundleResult",
    "DatasetBundle",
    "DatasetFile",
    "evaluate",
    "load_dataset_bundle",
    "AlgorithmConfig",
    "DayPartition",
    "ExperimentPolicy",
    "ExclusionReason",
    "PartitionStatus",
    "PredictionLedgerRow",
    "RollingDayCycle",
    "RollingExperiment",
    "RollingExperimentResult",
    "RollingLeaderboardRow",
    "SyntheticTimeConfig",
    "build_day_partitions",
    "cumulative_training_window",
    "partition_tables",
    "read_csv_to_table",
    "read_dataset_bundle_from_zip",
    "read_to_table",
    "run_batch",
    "run_batch_bundle",
    "run_bundle_experiment",
    "run_experiment",
    "run_rolling_experiment",
    "split_train_validate",
    "split_by_time",
]
