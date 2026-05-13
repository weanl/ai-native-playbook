"""TSBUADAdapter - bridges TSB-UAD algorithms to AnomalyDetector protocol.

Converts Table I/O to numpy arrays for TSB-UAD model consumption,
then converts decision_scores_ back to Table output following the
AnomalyDetector output contract.

M1 strategy:
- Single METRIC: sliding window → model.fit → decision_scores_ → align → threshold → label
- Multi METRIC: per-metric independent run, max/OR merge for global predicted_label
"""

from __future__ import annotations

import importlib
from typing import Any, ClassVar, Protocol

import numpy as np
import numpy.typing as npt
import pandas as pd

from nextaiops_algo.algorithms.adapters.tsbuad_configs import TSBUADAlgoConfig
from nextaiops_algo.core.algorithm import TaskType
from nextaiops_algo.core.table import FieldRole, Table, TableSchema


class _TSBUADModelProto(Protocol):
    """Minimal protocol for TSB-UAD model interface consumed by adapter."""

    decision_scores_: npt.NDArray[np.float64]

    def fit(self, X: npt.NDArray[np.float64]) -> None: ...


def _import_tsbuad_class(class_path: str) -> type[Any]:
    """Dynamically import a TSB-UAD model class from its dotted path.

    Args:
        class_path: e.g. "TSB_UAD.models.iforest.IForest"

    Returns:
        The imported class.

    Raises:
        ImportError: If TSB-UAD is not installed or class not found.
    """
    module_path, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls: type[Any] = getattr(module, class_name)
    return cls


def _find_window_length(series: npt.NDArray[np.float64]) -> int:
    """Determine optimal sliding window length for a time series.

    Uses TSB-UAD's find_length when available; falls back to a heuristic
    based on series length.

    Args:
        series: 1-D numpy array.

    Returns:
        Window length (integer, at least 2).
    """
    try:
        from TSB_UAD.utils.sliding_windows import find_length

        window: int = find_length(series)
        return max(2, window)
    except ImportError:
        # Fallback heuristic: sqrt of series length, clamped to [2, N//3]
        n = len(series)
        return max(2, min(int(np.sqrt(n)), n // 3))


def _sliding_window_convert(series: npt.NDArray[np.float64], window: int) -> npt.NDArray[np.float64]:
    """Convert a 1-D series to sliding window 2-D representation.

    Args:
        series: 1-D numpy array of length N.
        window: Window size.

    Returns:
        2-D array of shape (N - window + 1, window).
    """
    try:
        from TSB_UAD.utils.sliding_windows import Window

        converter = Window(window=window)
        result: npt.NDArray[np.float64] = converter.convert(series)
        return result
    except ImportError:
        # Manual sliding window
        n = len(series)
        length = n - window + 1
        out = np.empty((length, window), dtype=np.float64)
        for i in range(length):
            out[i] = series[i : i + window]
        return out


def _align_scores(
    scores: npt.NDArray[np.float64], original_length: int, window: int
) -> npt.NDArray[np.float64]:
    """Align window-level scores back to original point-level length.

    Strategy: assign each score to the last point of its window,
    then pad the first (window-1) positions with the first available score.

    Args:
        scores: Array of length (original_length - window + 1).
        original_length: Target length.
        window: Window size used for sliding window.

    Returns:
        Array of length original_length.
    """
    full_scores = np.zeros(original_length, dtype=np.float64)
    # Assign each score to position (i + window - 1)
    for i, s in enumerate(scores):
        full_scores[i + window - 1] = s
    # Pad first (window-1) positions with first score
    if window > 1 and len(scores) > 0:
        full_scores[: window - 1] = scores[0]
    return full_scores


def _apply_threshold(
    scores: npt.NDArray[np.float64],
    method: str = "sigma",
    n_sigma: float = 3.0,
    percentile: float = 98.0,
    fixed_value: float | None = None,
) -> tuple[float, float, npt.NDArray[np.intp]]:
    """Apply threshold strategy to anomaly scores, returning labels and bounds.

    Args:
        scores: Per-point anomaly scores.
        method: "sigma" | "percentile" | "fixed".
        n_sigma: Number of std deviations above mean (for sigma method).
        percentile: Percentile threshold (for percentile method).
        fixed_value: Fixed threshold value (for fixed method).

    Returns:
        Tuple of (threshold_upper, threshold_lower, predicted_labels).
        threshold_lower is always 0 (scores are non-negative by convention).
    """
    if method == "sigma":
        mean = float(np.mean(scores))
        std = float(np.std(scores))
        threshold_upper = mean + n_sigma * std
    elif method == "percentile":
        threshold_upper = float(np.percentile(scores, percentile))
    elif method == "fixed":
        if fixed_value is None:
            raise ValueError("fixed_value must be provided for 'fixed' threshold method")
        threshold_upper = fixed_value
    else:
        raise ValueError(f"Unknown threshold method: {method}")

    threshold_lower = 0.0
    predicted_labels: npt.NDArray[np.intp] = (scores > threshold_upper).astype(int)
    return threshold_upper, threshold_lower, predicted_labels


class TSBUADAdapter:
    """Adapter bridging TSB-UAD algorithms to the AnomalyDetector protocol.

    Wraps a TSB-UAD model class so that it accepts Table I/O and produces
    output conforming to the AnomalyDetector contract (predicted_label,
    anomaly_score, threshold columns).

    For multi-metric input, each metric column is processed independently
    with its own model instance, and predicted_labels are OR-merged.

    Attributes:
        name: REGISTRY name (e.g., "iforest").
        task_type: Always ANOMALY_DETECTION.
        required_input_roles: Always {METRIC}.
    """

    name: ClassVar[str]  # set per-instance from config
    task_type: ClassVar[TaskType] = TaskType.ANOMALY_DETECTION
    required_input_roles: ClassVar[set[FieldRole]] = {FieldRole.METRIC}

    def __init__(
        self,
        config: TSBUADAlgoConfig,
        algo_params: dict[str, object] | None = None,
    ) -> None:
        """Initialize adapter from a TSBUADAlgoConfig.

        Args:
            config: Algorithm configuration (class path, defaults, threshold).
            algo_params: Optional overrides for the model constructor params.
        """
        self._config = config
        # Merge default_params with user overrides
        self._algo_params = {**config.default_params, **(algo_params or {})}
        self._threshold_method = config.threshold_method
        self._threshold_params: dict[str, float | None] = {
            k: v if isinstance(v, (float, int)) else None for k, v in config.threshold_params.items()
        }
        # Per-metric state populated during fit()
        self._metric_models: dict[str, _TSBUADModelProto] = {}
        self._metric_windows: dict[str, int] = {}
        # Set name as instance attribute (Protocol expects ClassVar but
        # per-adapter names differ, so we override on the instance)
        self.__dict__["name"] = config.name

    def _create_model(self) -> _TSBUADModelProto:
        """Create a TSB-UAD model instance with configured params.

        Returns:
            New model instance satisfying _TSBUADModelProto.
        """
        cls = _import_tsbuad_class(self._config.algo_class_path)
        return cls(**self._algo_params)  # type: ignore[no-any-return]

    def fit(self, data: Table) -> None:
        """Train a TSB-UAD model for each METRIC column independently.

        For each metric:
        1. Extract series as numpy array
        2. Find optimal window length
        3. Convert to sliding window representation
        4. Create and fit a model instance

        Args:
            data: Input Table with at least one METRIC column.
        """
        metrics_df = data.metrics()
        self._metric_models = {}
        self._metric_windows = {}

        for col in metrics_df.columns:
            series = metrics_df[col].to_numpy(dtype=np.float64)
            # Handle NaN: fill with series mean to keep sliding window valid
            mean_val = float(np.nanmean(series))
            series = np.nan_to_num(series, nan=mean_val)

            window = _find_window_length(series)
            self._metric_windows[col] = window

            X = _sliding_window_convert(series, window)
            model = self._create_model()
            model.fit(X)
            self._metric_models[col] = model

    def detect(self, data: Table) -> Table:
        """Detect anomalies using fitted TSB-UAD models.

        For each metric:
        1. Extract series, convert to sliding window
        2. Read model.decision_scores_
        3. Align scores to original point-level length
        4. Apply threshold strategy → predicted_label per metric
        5. OR-merge across metrics for global predicted_label

        Args:
            data: Input Table to detect anomalies in.

        Returns:
            Table satisfying AnomalyDetector output contract.
        """
        metrics_df = data.metrics()
        n_rows = len(metrics_df)

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

        per_metric_labels: dict[str, npt.NDArray[np.intp]] = {}

        for col in metrics_df.columns:
            series = metrics_df[col].to_numpy(dtype=np.float64)
            mean_val = float(np.nanmean(series))
            series = np.nan_to_num(series, nan=mean_val)

            window = self._metric_windows[col]
            model = self._metric_models[col]

            # Get scores from model
            raw_scores = np.array(model.decision_scores_, dtype=np.float64)
            aligned_scores = _align_scores(raw_scores, n_rows, window)

            # Apply threshold
            n_sigma_val = self._threshold_params.get("n_sigma")
            percentile_val = self._threshold_params.get("percentile")
            fixed_val = self._threshold_params.get("fixed_value")

            threshold_upper, threshold_lower, metric_labels = _apply_threshold(
                aligned_scores,
                method=self._threshold_method,
                n_sigma=float(n_sigma_val) if n_sigma_val is not None else 3.0,
                percentile=float(percentile_val) if percentile_val is not None else 98.0,
                fixed_value=fixed_val,
            )

            per_metric_labels[col] = metric_labels

            output_df[f"{col}.anomaly_score"] = aligned_scores
            output_roles[f"{col}.anomaly_score"] = FieldRole.METRIC

            output_df[f"{col}.threshold_upper"] = threshold_upper
            output_roles[f"{col}.threshold_upper"] = FieldRole.METRIC

            output_df[f"{col}.threshold_lower"] = threshold_lower
            output_roles[f"{col}.threshold_lower"] = FieldRole.METRIC

        # OR-merge predicted_label across all metrics
        combined: npt.NDArray[np.intp] = np.zeros(n_rows, dtype=int)
        for metric_labels in per_metric_labels.values():
            combined = combined | metric_labels

        output_df["predicted_label"] = combined
        output_roles["predicted_label"] = FieldRole.LABEL

        schema = TableSchema(roles=output_roles)
        return Table(df=output_df, schema=schema)
