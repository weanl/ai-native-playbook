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
    """

    name: str
    algo_class_path: str
    default_params: dict[str, object] = field(default_factory=dict)
    threshold_method: str = "sigma"
    threshold_params: dict[str, object] = field(default_factory=dict)


# Default configs for the 5 first-party TSB-UAD algorithms.
TSBUAD_ALGO_CONFIGS: dict[str, TSBUADAlgoConfig] = {
    "iforest": TSBUADAlgoConfig(
        name="iforest",
        algo_class_path="TSB_UAD.models.iforest.IForest",
        default_params={},
        threshold_method="sigma",
        threshold_params={"n_sigma": 3},
    ),
    "lof": TSBUADAlgoConfig(
        name="lof",
        algo_class_path="TSB_UAD.models.lof.LOF",
        default_params={},
        threshold_method="sigma",
        threshold_params={"n_sigma": 3},
    ),
    "ocsvm": TSBUADAlgoConfig(
        name="ocsvm",
        algo_class_path="TSB_UAD.models.ocsvm.OCSVM",
        default_params={},
        threshold_method="sigma",
        threshold_params={"n_sigma": 3},
    ),
    "pca": TSBUADAlgoConfig(
        name="pca",
        algo_class_path="TSB_UAD.models.pca.PCA",
        default_params={},
        threshold_method="sigma",
        threshold_params={"n_sigma": 3},
    ),
    "hbos": TSBUADAlgoConfig(
        name="hbos",
        algo_class_path="TSB_UAD.models.hbos.HBOS",
        default_params={},
        threshold_method="sigma",
        threshold_params={"n_sigma": 3},
    ),
}
