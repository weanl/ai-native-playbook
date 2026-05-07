"""NextAIOpsAlgoApp - Algorithm Platform for NextAIOpsSystem.

This package provides the algorithm platform subsystem for NextAIOpsSystem,
supporting anomaly detection algorithm development, experiment tracking,
and visualization capabilities.

Modules:
    core: Stable layer contracts (Table, Algorithm protocols, data models)
    algorithms: Algorithm plugin layer (registry, implementations)
    pipeline: Experiment orchestration (preprocess, run, evaluate)
    viz: Visualization (timeseries plots)
    storage: Persistence layer (SQLite tracking, file system artifacts)
    cli: Command-line interface
    ui: Streamlit web interface
"""

__version__ = "0.1.0"
__author__ = "NextAIOps Team"
