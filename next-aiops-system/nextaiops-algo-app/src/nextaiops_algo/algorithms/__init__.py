"""Algorithms module - Algorithm plugin layer.

This module provides the algorithm plugin mechanism for NextAIOpsAlgoApp:
- Registry: Central registry for algorithm discovery
- Base: Task-specific protocols (AnomalyDetector for M0)
- Implementations: Concrete algorithm implementations (3-Sigma, IQR, etc.)

All algorithms must:
- Implement core.Algorithm protocol + task-specific subprotocol
- Register via algorithms.registry.REGISTRY
- Use Table I/O (no direct storage access)
"""

from nextaiops_algo.algorithms.base import AnomalyDetector
from nextaiops_algo.algorithms.iqr import IQR
from nextaiops_algo.algorithms.registry import REGISTRY, get_algorithm, list_algorithms, register
from nextaiops_algo.algorithms.three_sigma import ThreeSigma

__all__ = ["AnomalyDetector", "IQR", "REGISTRY", "get_algorithm", "list_algorithms", "register", "ThreeSigma"]
