"""CLI module - Command-line interface.

This module provides CLI entry points for NextAIOpsAlgoApp:
- run: Execute experiment (data + algorithm + params)
- list-algos: Show registered algorithms
- list-runs: Show experiment run history

CLI wraps pipeline.run_experiment and storage queries.
"""
