"""Core module - Stable layer contracts.

This module defines the stable layer contracts for NextAIOpsAlgoApp:
- Table: Unified data carrier (DataFrame + Schema)
- Algorithm: Three-layer protocol (base + task-specific)
- Experiment: Run tracking data models
- Storage: Tracking and artifact store protocols

Changes to interfaces in this module require ADR approval.
"""

from .algorithm import Algorithm, TaskType
from .exceptions import NextAIOpsError, SchemaValidationError
from .experiment import ExperimentRun, RunResult, RunStatus
from .storage_iface import ArtifactStore
from .table import FieldRole, Table, TableSchema
from .tracking import TrackingStore

__all__ = [
    "Algorithm",
    "ArtifactStore",
    "ExperimentRun",
    "FieldRole",
    "NextAIOpsError",
    "RunResult",
    "RunStatus",
    "SchemaValidationError",
    "Table",
    "TableSchema",
    "TaskType",
    "TrackingStore",
]
