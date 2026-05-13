"""Experiment run and batch run data models."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class RunStatus(StrEnum):
    """Status of an experiment run."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BatchStatus(StrEnum):
    """Status of a batch experiment run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL_FAILED = "partial_failed"
    FAILED = "failed"


class ExperimentRun(BaseModel):
    """Record of a single experiment run.

    Attributes:
        run_id: Unique identifier for the run.
        dataset_version: Version or identifier of the input dataset.
        algorithm_name: Name of the algorithm used.
        params: Algorithm parameters as a dict (structure not fixed in core).
        status: Current status of the run.
        artifacts_path: Path to the directory containing run artifacts.
        created_at: Timestamp when the run was created.
    """

    run_id: str
    dataset_version: str
    algorithm_name: str
    params: dict[str, Any]
    status: RunStatus
    artifacts_path: str
    created_at: datetime


class RunResult(BaseModel):
    """Result of a completed experiment run.

    Attributes:
        run_id: Unique identifier for the run.
        metrics: Evaluation metrics as a dict (e.g., {"precision": 0.8, "f1": 0.75}).
        artifacts_path: Path to the directory containing run artifacts.
    """

    run_id: str
    metrics: dict[str, float]
    artifacts_path: str


class BatchRun(BaseModel):
    """Record of a batch experiment (multiple algorithms × single dataset).

    Attributes:
        batch_id: Unique identifier for the batch.
        dataset_source: Path or name of the input dataset.
        algorithm_names: List of algorithm names included in the batch.
        created_at: Timestamp when the batch was created.
        runs: List of ExperimentRun records for each algorithm in the batch.
        status: Overall status of the batch.
    """

    batch_id: str
    dataset_source: str
    algorithm_names: list[str]
    created_at: datetime
    runs: list[ExperimentRun]
    status: BatchStatus
