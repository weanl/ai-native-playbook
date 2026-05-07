"""Storage module - Persistence layer.

This module provides persistence capabilities for NextAIOpsAlgoApp:
- sqlite_tracking: Run tracking with SQLite backend
- fs_artifact: File system artifact storage

Default storage path: ./nextaiops_algo/runs/<run_id>/
Configurable via NEXTAIOPS_ALGO_HOME environment variable.
"""