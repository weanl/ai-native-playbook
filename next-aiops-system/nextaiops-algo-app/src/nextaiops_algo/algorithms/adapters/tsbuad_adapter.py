"""TSBUADAdapter - bridges TSB-UAD algorithms to AnomalyDetector protocol.

Converts Table I/O to numpy arrays for TSB-UAD model consumption,
then scores test data using per-model hooks to produce anomaly scores,
aligned back to point-level length, thresholded, and output as Table.

Scoring strategies (per-model, due to TSB-UAD API inconsistencies):
- iforest: sklearn detector_.decision_function(X_test), negate
- lof:     create sklearn LocalOutlierFactor(novelty=True) directly
- ocsvm:   fit(X_train, X_train), then detector_.decision_function(X_test), negate
- pca:     manual reconstruction error from scaler_ + selected_components_
- hbos:    _calculate_outlier_scores on test data, invert and sum

M1 multi-metric strategy: per-metric independent run, OR merge for global predicted_label.
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
    """Dynamically import a TSB-UAD model class from its dotted path."""
    module_path, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls: type[Any] = getattr(module, class_name)
    return cls


def _find_window_length(series: npt.NDArray[np.float64]) -> int:
    """Determine optimal sliding window length for a time series.

    Uses TSB-UAD's find_length when available; falls back to heuristic.
    """
    try:
        from TSB_UAD.utils.sliding_windows import find_length

        window: int = find_length(series)
        return max(2, window)
    except ImportError:
        n = len(series)
        return max(2, min(int(np.sqrt(n)), n // 3))


def _sliding_window_convert(
    series: npt.NDArray[np.float64], window: int
) -> npt.NDArray[np.float64]:
    """Convert a 1-D series to sliding window 2-D representation."""
    try:
        from TSB_UAD.utils.sliding_windows import Window

        converter = Window(window=window)
        result: npt.NDArray[np.float64] = converter.convert(series)
        return result
    except ImportError:
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

    Strategy: assign each score to the center of its window,
    which reduces positional shift compared to end-of-window alignment.
    """
    if len(scores) == 0:
        return np.zeros(original_length, dtype=np.float64)

    full_scores = np.zeros(original_length, dtype=np.float64)
    center_offset = window // 2
    # Assign each score to position (i + center_offset)
    for i in range(len(scores)):
        pos = i + center_offset
        if pos < original_length:
            full_scores[pos] = scores[i]
    # Pad first center_offset positions with first score
    if window > 1 and len(scores) > 0:
        full_scores[:center_offset] = scores[0]
    # Pad trailing positions with last score
    last_filled = len(scores) - 1 + center_offset
    if last_filled < original_length - 1:
        full_scores[last_filled + 1 :] = scores[-1]
    return full_scores


def _apply_threshold(
    scores: npt.NDArray[np.float64],
    method: str = "sigma",
    n_sigma: float = 3.0,
    percentile: float = 98.0,
    fixed_value: float | None = None,
) -> tuple[float, float, npt.NDArray[np.intp]]:
    """Apply threshold strategy to anomaly scores, returning labels and bounds."""
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


def _score_iforest(model: Any, X_test: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    """Score test data using IForest's underlying sklearn model."""
    return np.asarray(-model.detector_.decision_function(X_test), dtype=np.float64)


def _score_ocsvm(
    model: Any, X_train: npt.NDArray[np.float64], X_test: npt.NDArray[np.float64]
) -> npt.NDArray[np.float64]:
    """Score test data using OCSVM's underlying sklearn OneClassSVM."""
    return np.asarray(-model.detector_.decision_function(X_test), dtype=np.float64)


def _score_lof(
    X_train: npt.NDArray[np.float64], X_test: npt.NDArray[np.float64]
) -> npt.NDArray[np.float64]:
    """Score test data using sklearn LOF with novelty=True."""
    from sklearn.neighbors import LocalOutlierFactor

    model = LocalOutlierFactor(n_neighbors=20, novelty=True, contamination=0.1)
    model.fit(X_train)
    return np.asarray(-model.decision_function(X_test), dtype=np.float64)


def _score_pca(model: Any, X_test: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    """Score test data using PCA reconstruction error."""
    X_scaled = model.scaler_.transform(X_test)
    components = model.selected_components_
    X_proj = np.dot(X_scaled, components.T)
    X_recon = np.dot(X_proj, components)
    return np.asarray(np.sum((X_scaled - X_recon) ** 2, axis=1), dtype=np.float64)


def _score_hbos(model: Any, X_test: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    """Score test data using HBOS histograms.

    TSB-UAD HBOS computes outlier_scores where lower values indicate
    anomalous points. We negate the summed outlier_scores to convert
    to our convention: higher = more anomalous.
    """
    from TSB_UAD.models.hbos import _calculate_outlier_scores

    outlier_scores = _calculate_outlier_scores(
        X_test, model.bin_edges_, model.hist_, model.n_bins, model.alpha, model.tol
    )
    return np.asarray(-np.sum(outlier_scores, axis=1), dtype=np.float64)


class TSBUADAdapter:
    """Adapter bridging TSB-UAD algorithms to the AnomalyDetector protocol.

    Wraps a TSB-UAD model class so that it accepts Table I/O and produces
    output conforming to the AnomalyDetector contract.

    For multi-metric input, each metric column is processed independently
    with its own model instance, and predicted_labels are OR-merged.
    """

    name: ClassVar[str]
    task_type: ClassVar[TaskType] = TaskType.ANOMALY_DETECTION
    required_input_roles: ClassVar[set[FieldRole]] = {FieldRole.METRIC}

    def __init__(
        self,
        config: TSBUADAlgoConfig,
        algo_params: dict[str, object] | None = None,
    ) -> None:
        """Initialize adapter from a TSBUADAlgoConfig."""
        self._config = config
        self._scoring_method = config.scoring_method
        # Merge default_params with user overrides
        self._algo_params = {**config.default_params, **(algo_params or {})}
        # Fix HBOS alpha/tol: TSB-UAD requires np.float64, not Python float
        if self._scoring_method == "hbos":
            alpha_raw = self._algo_params.get("alpha")
            if alpha_raw is None:
                self._algo_params["alpha"] = np.float64(0.1)
            else:
                self._algo_params["alpha"] = np.float64(float(str(alpha_raw)))
            tol_raw = self._algo_params.get("tol")
            if tol_raw is None:
                self._algo_params["tol"] = np.float64(0.5)
            else:
                self._algo_params["tol"] = np.float64(float(str(tol_raw)))
        self._threshold_method = config.threshold_method
        self._threshold_params: dict[str, float | None] = {
            k: float(v) if isinstance(v, (float, int)) else None
            for k, v in config.threshold_params.items()
        }
        # Per-metric state populated during fit()
        self._metric_models: dict[str, Any] = {}
        self._metric_windows: dict[str, int] = {}
        self._metric_train_data: dict[str, npt.NDArray[np.float64]] = {}
        # Set name as instance attribute
        self.__dict__["name"] = config.name

    def _create_model(self) -> Any:
        """Create a TSB-UAD model instance with configured params."""
        cls = _import_tsbuad_class(self._config.algo_class_path)
        return cls(**self._algo_params)

    def _fit_model(self, model: Any, X: npt.NDArray[np.float64]) -> None:
        """Fit model with per-algorithm hooks.

        OCSVM requires X_test as second argument to fit().
        """
        if self._scoring_method == "ocsvm":
            model.fit(X, X)
        else:
            model.fit(X)

    def _score_test(
        self,
        model: Any,
        X_train: npt.NDArray[np.float64],
        X_test: npt.NDArray[np.float64],
    ) -> npt.NDArray[np.float64]:
        """Compute anomaly scores on test data using per-model scoring hook."""
        if self._scoring_method == "detector_decision_function":
            return _score_iforest(model, X_test)
        if self._scoring_method == "ocsvm":
            return _score_ocsvm(model, X_train, X_test)
        if self._scoring_method == "lof":
            return _score_lof(X_train, X_test)
        if self._scoring_method == "pca":
            return _score_pca(model, X_test)
        if self._scoring_method == "hbos":
            return _score_hbos(model, X_test)
        raise ValueError(f"Unknown scoring method: {self._scoring_method}")

    def fit(self, data: Table) -> None:
        """Train a TSB-UAD model for each METRIC column independently.

        Uses consistent window length derived from training data for both
        fit and detect, ensuring feature dimension compatibility.
        """
        metrics_df = data.metrics()
        self._metric_models = {}
        self._metric_windows = {}
        self._metric_train_data = {}

        for col in metrics_df.columns:
            series = metrics_df[col].to_numpy(dtype=np.float64)
            mean_val = float(np.nanmean(series))
            series = np.nan_to_num(series, nan=mean_val)

            window = _find_window_length(series)
            self._metric_windows[col] = window

            X = _sliding_window_convert(series, window)
            # Store train sliding window for scoring
            self._metric_train_data[col] = X

            # LOF uses sklearn directly, no TSB-UAD model needed for fit
            if self._scoring_method != "lof":
                model = self._create_model()
                self._fit_model(model, X)
                self._metric_models[col] = model

    def detect(self, data: Table) -> Table:
        """Detect anomalies using fitted TSB-UAD models.

        Scores test data using per-model scoring hooks on test sliding window,
        then aligns window-level scores to point-level and applies threshold.
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

            # Use consistent window from training data for test conversion
            X_test = _sliding_window_convert(series, window)
            X_train = self._metric_train_data[col]

            if self._scoring_method == "lof":
                # LOF doesn't store a model — scored directly on test data
                raw_scores = self._score_test(None, X_train, X_test)
            else:
                model = self._metric_models[col]
                raw_scores = self._score_test(model, X_train, X_test)

            # Align window-level scores to original point-level length
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
