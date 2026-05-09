"""AnomalyDetector - task-specific protocol for anomaly detection algorithms."""

from typing import ClassVar, Protocol

from nextaiops_algo.core.algorithm import Algorithm, TaskType
from nextaiops_algo.core.table import FieldRole, Table


class AnomalyDetector(Algorithm, Protocol):
    """Task-specific protocol for anomaly detection algorithms.

    Extends the base Algorithm protocol with fit/detect methods.
    All anomaly detection algorithms must implement this protocol.

    Output Table Contract (see AGENTS.md §9.3):
        Required columns:
            - predicted_label (role LABEL, int ∈ {0, 1})
              Multi-metric: OR merge (any metric exceeds threshold → 1)
              Single-metric: degenerate to that metric's label

        Recommended columns (optional, graceful degradation in viz):
            - timestamp (role TIMESTAMP, if input has it, copy row-by-row)
            - Input METRIC columns (role METRIC, original names preserved)
            - <metric>.anomaly_score (role METRIC, continuous score for that metric)
            - <metric>.threshold_upper / <metric>.threshold_lower (role METRIC)

        Alignment constraints (mandatory):
            - Output Table rows == Input Table rows
            - If input has TIMESTAMP, output must have same TIMESTAMP column,
              with identical values and order

    Class Attributes:
        name: Unique identifier for the algorithm (inherited from Algorithm).
        task_type: Always TaskType.ANOMALY_DETECTION.
        required_input_roles: Always {FieldRole.METRIC}.

    Note:
        This is a Protocol, not a base class. Algorithms can implement it
        without inheritance. runtime_checkable allows isinstance() checks.
    """

    task_type: ClassVar[TaskType] = TaskType.ANOMALY_DETECTION
    required_input_roles: ClassVar[set[FieldRole]] = {FieldRole.METRIC}

    def fit(self, data: Table) -> None:
        """Train the anomaly detector on historical data.

        Args:
            data: Input Table with at least one METRIC column.
                  Algorithm should handle single or multiple METRIC columns.
        """
        ...

    def detect(self, data: Table) -> Table:
        """Detect anomalies in the input data.

        Args:
            data: Input Table with at least one METRIC column.

        Returns:
            Table satisfying AnomalyDetector output contract:
                - predicted_label column (role LABEL)
                - Same row count as input
                - If input has timestamp, output includes it row-by-row
                - Optional: anomaly scores, thresholds for each metric
        """
        ...
