"""Tracking store protocol - interface for experiment tracking."""

from typing import Protocol

from .experiment import ExperimentRun


class TrackingStore(Protocol):
    """Protocol for tracking experiment runs.

    Implementations store run records and allow querying by run_id or listing runs.
    """

    def log_run(self, run: ExperimentRun) -> None:
        """Log a new experiment run.

        Args:
            run: The ExperimentRun to log.
        """
        ...

    def get_run(self, run_id: str) -> ExperimentRun | None:
        """Retrieve an experiment run by its ID.

        Args:
            run_id: The unique identifier of the run.

        Returns:
            The ExperimentRun if found, else None.
        """
        ...

    def list_runs(self, limit: int | None = None) -> list[ExperimentRun]:
        """List experiment runs, optionally limited.

        Args:
            limit: Maximum number of runs to return. None means all runs.

        Returns:
            List of ExperimentRun records, ordered by creation time (newest first).
        """
        ...
