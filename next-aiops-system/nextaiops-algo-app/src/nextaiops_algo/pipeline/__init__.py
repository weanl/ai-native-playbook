"""Pipeline module - Experiment orchestration layer.

This module provides the orchestration layer for NextAIOpsAlgoApp:
- preprocess: CSV → Table conversion + time-series split
- run: run_experiment main entry point
- evaluate: Metrics calculation (precision/recall/F1)

Pipeline does not directly import algorithm implementations;
it accesses algorithms via algorithms.registry.REGISTRY only.
"""