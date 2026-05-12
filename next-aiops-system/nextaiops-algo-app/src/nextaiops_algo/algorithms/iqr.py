"""IQR (Interquartile Range) anomaly detection algorithm."""

from typing import ClassVar

import numpy as np
import pandas as pd

from nextaiops_algo.algorithms.base import AnomalyDetector
from nextaiops_algo.algorithms.registry import register
from nextaiops_algo.core.algorithm import TaskType
from nextaiops_algo.core.table import FieldRole, Table, TableSchema


@register
class IQR(AnomalyDetector):
    """IQR anomaly detection algorithm.

    Detects anomalies using the Interquartile Range method. Values outside
    [Q1 - k*IQR, Q3 + k*IQR] are flagged as anomalies. Supports both single
    and multiple METRIC columns.

    For each METRIC column:
        - fit: computes Q1, Q3, IQR = Q3 - Q1
        - detect: marks values outside [Q1 - k*IQR, Q3 + k*IQR] as anomalies

    When IQR = 0 (constant or near-constant series), the threshold degrades
    to [Q1, Q3] so that values outside the observed range are still detected.

    Attributes:
        name: "iqr"
        task_type: ANOMALY_DETECTION
        required_input_roles: {METRIC}
        _stats: Dict mapping metric column name to (Q1, Q3, IQR) tuple.
    """

    name: ClassVar[str] = "iqr"
    task_type: ClassVar[TaskType] = TaskType.ANOMALY_DETECTION
    required_input_roles: ClassVar[set[FieldRole]] = {FieldRole.METRIC}

    def __init__(self, k: float = 1.5) -> None:
        """Initialize IQR detector.

        Args:
            k: Multiplier for IQR to define threshold bounds.
                Default 1.5 (standard outlier detection threshold).
        """
        self._k = k
        self._stats: dict[str, tuple[float, float, float]] = {}

    def fit(self, data: Table) -> None:
        """Compute Q1, Q3, IQR for each METRIC column.

        Args:
            data: Input Table with at least one METRIC column.
        """
        metrics_df = data.metrics()
        for col in metrics_df.columns:
            q1 = float(metrics_df[col].quantile(0.25))
            q3 = float(metrics_df[col].quantile(0.75))
            iqr = q3 - q1
            self._stats[col] = (q1, q3, iqr)

    def detect(self, data: Table) -> Table:
        """Detect anomalies using IQR rule for each METRIC column.

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

        output_df = pd.DataFrame(index=range(n_rows))
        output_roles: dict[str, FieldRole] = {}

        timestamps = data.timestamps()
        if timestamps is not None:
            output_df["timestamp"] = timestamps.values
            output_roles["timestamp"] = FieldRole.TIMESTAMP

        for col in metrics_df.columns:
            output_df[col] = metrics_df[col].values
            output_roles[col] = FieldRole.METRIC

        per_metric_labels: dict[str, pd.Series] = {}

        for col in metrics_df.columns:
            q1, q3, iqr = self._stats[col]

            threshold_lower = q1 - self._k * iqr
            threshold_upper = q3 + self._k * iqr

            # Degradation when IQR=0: threshold becomes [Q1, Q3]
            # Values outside observed range are still anomalies
            effective_iqr = iqr if iqr > 0 else 1.0
            anomaly_score = np.maximum(
                (metrics_df[col].values - q3) / effective_iqr,
                (q1 - metrics_df[col].values) / effective_iqr,
            )
            anomaly_score = np.where(anomaly_score < 0, 0.0, anomaly_score)
            anomaly_score = pd.Series(anomaly_score).fillna(0.0)

            is_anomaly = (
                (metrics_df[col] > threshold_upper)
                | (metrics_df[col] < threshold_lower)
            )
            per_metric_labels[col] = is_anomaly.astype(int)

            output_df[f"{col}.anomaly_score"] = anomaly_score.values
            output_roles[f"{col}.anomaly_score"] = FieldRole.METRIC

            output_df[f"{col}.threshold_upper"] = threshold_upper
            output_roles[f"{col}.threshold_upper"] = FieldRole.METRIC

            output_df[f"{col}.threshold_lower"] = threshold_lower
            output_roles[f"{col}.threshold_lower"] = FieldRole.METRIC

        combined_label = pd.Series([0] * n_rows, index=metrics_df.index, dtype=int)
        for col_labels in per_metric_labels.values():
            combined_label = combined_label | col_labels

        output_df["predicted_label"] = combined_label.reset_index(drop=True).values
        output_roles["predicted_label"] = FieldRole.LABEL

        schema = TableSchema(roles=output_roles)
        return Table(df=output_df, schema=schema)
