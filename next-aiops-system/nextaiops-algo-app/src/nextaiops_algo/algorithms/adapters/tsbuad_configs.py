"""TSB-UAD algorithm configurations - default parameters and metadata for each bridged algorithm."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TSBUADAlgoConfig:
    """Configuration for a single TSB-UAD algorithm bridge.

    Attributes:
        name: REGISTRY name (e.g., "iforest").
        algo_class_path: Dotted import path to the TSB-UAD model class.
        default_params: Keyword arguments passed to the TSB-UAD model constructor.
        threshold_method: Default threshold strategy for converting scores to labels.
        threshold_params: Extra parameters for the threshold method.
        scoring_method: How to compute anomaly scores on test data.
            - "detector_decision_function": use sklearn detector_.decision_function(X_test), negate
            - "ocsvm": fit(X_train, X_train), then detector_.decision_function(X_test), negate
            - "lof": create sklearn LOF(novelty=True) directly, then decision_function(X_test), negate
            - "pca": manual reconstruction error from model.scaler_ + model.selected_components_
            - "hbos": use TSB-UAD's _calculate_outlier_scores on test data
    """

    name: str
    algo_class_path: str
    default_params: dict[str, object] = field(default_factory=dict)
    threshold_method: str = "sigma"
    threshold_params: dict[str, object] = field(default_factory=dict)
    scoring_method: str = "detector_decision_function"


# Default configs for the 5 first-party TSB-UAD algorithms.
TSBUAD_ALGO_CONFIGS: dict[str, TSBUADAlgoConfig] = {
    "iforest": TSBUADAlgoConfig(
        name="iforest",
        algo_class_path="TSB_UAD.models.iforest.IForest",
        default_params={},
        threshold_method="percentile",
        threshold_params={"percentile": 95},
        scoring_method="detector_decision_function",
    ),
    "lof": TSBUADAlgoConfig(
        name="lof",
        algo_class_path="TSB_UAD.models.lof.LOF",
        default_params={},
        threshold_method="sigma",
        threshold_params={"n_sigma": 3},
        scoring_method="lof",
    ),
    "ocsvm": TSBUADAlgoConfig(
        name="ocsvm",
        algo_class_path="TSB_UAD.models.ocsvm.OCSVM",
        default_params={},
        threshold_method="sigma",
        threshold_params={"n_sigma": 3},
        scoring_method="ocsvm",
    ),
    "pca": TSBUADAlgoConfig(
        name="pca",
        algo_class_path="TSB_UAD.models.pca.PCA",
        default_params={"n_selected_components": None},
        threshold_method="sigma",
        threshold_params={"n_sigma": 3},
        scoring_method="pca",
    ),
    "hbos": TSBUADAlgoConfig(
        name="hbos",
        algo_class_path="TSB_UAD.models.hbos.HBOS",
        default_params={"alpha": None, "tol": None},
        threshold_method="percentile",
        threshold_params={"percentile": 97},
        scoring_method="hbos",
    ),
}
