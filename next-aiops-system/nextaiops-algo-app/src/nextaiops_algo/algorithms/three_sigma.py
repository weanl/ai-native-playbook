"""Three Sigma anomaly detection algorithm."""

from typing import ClassVar

import pandas as pd

from nextaiops_algo.algorithms.base import AnomalyDetector
from nextaiops_algo.algorithms.registry import register
from nextaiops_algo.core.algorithm import TaskType
from nextaiops_algo.core.table import FieldRole, Table, TableSchema


@register
class ThreeSigma(AnomalyDetector):
    """3-Sigma anomaly detection algorithm.

    Detects anomalies by identifying values that exceed 3 standard deviations
    from the mean. Supports both single and multiple METRIC columns.

    For each METRIC column:
        - fit: computes mean and std
        - detect: marks values outside [mean - 3*std, mean + 3*std] as anomalies

    Attributes:
        name: "three_sigma"
        task_type: ANOMALY_DETECTION
        required_input_roles: {METRIC}
        _stats: Dict mapping metric column name to (mean, std) tuple.
    """

    name: ClassVar[str] = "three_sigma"
    task_type: ClassVar[TaskType] = TaskType.ANOMALY_DETECTION
    required_input_roles: ClassVar[set[FieldRole]] = {FieldRole.METRIC}

    def __init__(self) -> None:
        """Initialize ThreeSigma detector."""
        self._stats: dict[str, tuple[float, float]] = {}

    def fit(self, data: Table) -> None:
        """Compute mean and std for each METRIC column.

        Args:
            data: Input Table with at least one METRIC column.
        """
        metrics_df = data.metrics()
        for col in metrics_df.columns:
            mean = float(metrics_df[col].mean())
            std = float(metrics_df[col].std())
            self._stats[col] = (mean, std)

    def detect(self, data: Table) -> Table:
        """Detect anomalies using 3-sigma rule for each METRIC column.

        Args:
            data: Input Table to detect anomalies in.

        Returns:
            Table with:
                - predicted_label (role LABEL, OR-merged across all metrics)
                - Original METRIC columns preserved
                - <metric>.anomaly_score for each metric
                - <metric>.threshold_upper / threshold_lower for each metric
                - timestamp (if input has it, copied row-by-row)
        """
        metrics_df = data.metrics()
        n_rows = len(metrics_df)

        # Build output DataFrame
        output_df = pd.DataFrame(index=range(n_rows))
        output_roles: dict[str, FieldRole] = {}

        # Copy timestamp if present
        timestamps = data.timestamps()
        if timestamps is not None:
            output_df["timestamp"] = timestamps.values
            output_roles["timestamp"] = FieldRole.TIMESTAMP

        # Copy original metric columns
        for col in metrics_df.columns:
            output_df[col] = metrics_df[col].values
            output_roles[col] = FieldRole.METRIC

        # For each metric, compute anomaly labels and scores
        per_metric_labels: dict[str, pd.Series] = {}

        for col in metrics_df.columns:
            mean, std = self._stats[col]

            threshold_upper = mean + 3 * std
            threshold_lower = mean - 3 * std

            # Anomaly score: absolute deviation from mean / std
            anomaly_score = ((metrics_df[col] - mean).abs() / std).fillna(0.0)

            # Anomaly label: 1 if outside [lower, upper]
            is_anomaly = (
                (metrics_df[col] > threshold_upper) |
                (metrics_df[col] < threshold_lower)
            )
            per_metric_labels[col] = is_anomaly.astype(int)

            # Add score and thresholds
            output_df[f"{col}.anomaly_score"] = anomaly_score.values
            output_roles[f"{col}.anomaly_score"] = FieldRole.METRIC

            output_df[f"{col}.threshold_upper"] = threshold_upper
            output_roles[f"{col}.threshold_upper"] = FieldRole.METRIC

            output_df[f"{col}.threshold_lower"] = threshold_lower
            output_roles[f"{col}.threshold_lower"] = FieldRole.METRIC

        # OR-merge predicted_label across all metrics
        # Use the same index as metrics_df to avoid index alignment issues
        combined_label = pd.Series([0] * n_rows, index=metrics_df.index, dtype=int)
        for col_labels in per_metric_labels.values():
            combined_label = combined_label | col_labels

        # Reset index to range for output DataFrame
        output_df["predicted_label"] = combined_label.reset_index(drop=True).values
        output_roles["predicted_label"] = FieldRole.LABEL

        # Create output schema and Table
        schema = TableSchema(roles=output_roles)
        return Table(df=output_df, schema=schema)
