"""Core exceptions for NextAIOpsAlgoApp."""

from typing import Any


class NextAIOpsError(Exception):
    """Base exception for all NextAIOpsAlgoApp errors.

    All domain-specific exceptions should inherit from this class.
    Carries context information for debugging (run_id, dataset_id, etc.).
    """

    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.context = context or {}


class SchemaValidationError(NextAIOpsError):
    """Raised when Table schema validation fails.

    Common causes:
    - No METRIC columns in Table
    - More than 1 TIMESTAMP or LABEL column
    - Column names in roles not present in DataFrame
    - Missing required columns for algorithm input
    """

    pass
