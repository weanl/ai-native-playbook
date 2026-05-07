"""Algorithms module - Algorithm plugin layer.

This module provides the algorithm plugin mechanism for NextAIOpsAlgoApp:
- Registry: Central registry for algorithm discovery
- Base: Task-specific protocols (AnomalyDetector for M0)
- Implementations: Concrete algorithm implementations (3-Sigma, etc.)

All algorithms must:
- Implement core.Algorithm protocol + task-specific subprotocol
- Register via algorithms.registry.REGISTRY
- Use Table I/O (no direct storage access)
"""
