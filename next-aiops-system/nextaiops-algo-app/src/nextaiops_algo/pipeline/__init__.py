"""Pipeline module - Experiment orchestration layer.

This module provides the orchestration layer for NextAIOpsAlgoApp:
- preprocess: CSV → Table conversion + time-series split
- run: run_experiment main entry point
- batch: run_batch for multi-algorithm experiments
- evaluate: Metrics calculation (precision/recall/F1)

Pipeline does not directly import algorithm implementations;
it accesses algorithms via algorithms.registry.REGISTRY only.
"""

from .batch import run_batch
from .evaluate import evaluate
from .preprocess import read_csv_to_table, read_to_table, split_by_time
from .run import run_experiment

__all__ = [
    "evaluate",
    "read_csv_to_table",
    "read_to_table",
    "run_batch",
    "run_experiment",
    "split_by_time",
]
