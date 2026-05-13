"""Algorithms module - Algorithm plugin layer.

This module provides the algorithm plugin mechanism for NextAIOpsAlgoApp:
- Registry: Central registry for algorithm discovery
- Base: Task-specific protocols (AnomalyDetector for M0)
- Implementations: Concrete algorithm implementations (3-Sigma, IQR, etc.)
- Adapters: Bridge external libraries (TSB-UAD) to AnomalyDetector protocol

All algorithms must:
- Implement core.Algorithm protocol + task-specific subprotocol
- Register via algorithms.registry.REGISTRY
- Use Table I/O (no direct storage access)
"""

from nextaiops_algo.algorithms.adapters.tsbuad_adapter import TSBUADAdapter

# Conditionally register TSB-UAD algorithms when the optional dependency is installed.
# This import is safe: if TSB-UAD is not installed, registration is silently skipped.
from nextaiops_algo.algorithms.adapters.tsbuad_registry import register_tsbuad_algorithms
from nextaiops_algo.algorithms.base import AnomalyDetector
from nextaiops_algo.algorithms.iqr import IQR
from nextaiops_algo.algorithms.params import AlgorithmParamSpec
from nextaiops_algo.algorithms.registry import (
    REGISTRY,
    create_algorithm,
    get_algorithm,
    get_algorithm_param_specs,
    list_algorithms,
    normalize_algorithm_params,
    register,
)
from nextaiops_algo.algorithms.three_sigma import ThreeSigma

register_tsbuad_algorithms()

__all__ = [
    "AnomalyDetector",
    "AlgorithmParamSpec",
    "create_algorithm",
    "IQR",
    "REGISTRY",
    "TSBUADAdapter",
    "get_algorithm",
    "get_algorithm_param_specs",
    "list_algorithms",
    "normalize_algorithm_params",
    "register",
    "register_tsbuad_algorithms",
    "ThreeSigma",
]
