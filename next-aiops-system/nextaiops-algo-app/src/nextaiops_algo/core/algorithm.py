"""Algorithm protocol - base contract for all algorithms."""

from enum import StrEnum
from typing import ClassVar, Protocol, runtime_checkable

from .table import FieldRole


class TaskType(StrEnum):
    """Type of task an algorithm performs.

    M0 only supports ANOMALY_DETECTION. New task types require ADR.
    """

    ANOMALY_DETECTION = "anomaly_detection"


@runtime_checkable
class Algorithm(Protocol):
    """Base protocol for all algorithms.

    All algorithms must implement this protocol and register in REGISTRY.
    This protocol defines the cross-task minimum contract.

    Class Attributes:
        name: Unique identifier for the algorithm (used in REGISTRY and CLI).
        task_type: The type of task this algorithm performs.
        required_input_roles: Set of FieldRoles that must be present in input Table.

    Note:
        This is a Protocol, not a base class. Algorithms can implement it
        without inheritance. runtime_checkable allows isinstance() checks.
    """

    name: ClassVar[str]
    task_type: ClassVar[TaskType]
    required_input_roles: ClassVar[set[FieldRole]]
