"""Viz module - Visualization layer.

This module provides visualization capabilities for NextAIOpsAlgoApp:
- timeseries: Time-series plots with anomaly markers
- preview: Input data preview with ground-truth anomaly labels
- leaderboard: Batch experiment ranked DataFrame
- overlay: Multi-algorithm detection overlay comparison
- heatmap: Algorithm × metrics matrix heatmap
- batch_bundle: Algorithm × file DatasetBundle batch result views

Visualization outputs pure HTML files (Plotly), independent of web frameworks.
Graceful degradation for missing columns (timestamp, thresholds, scores).
"""

from .batch_bundle import (
    build_file_batch_view,
    render_bundle_algorithm_leaderboard,
    render_bundle_file_matrix,
    render_bundle_heatmap,
)
from .heatmap import render_heatmap
from .leaderboard import render_leaderboard
from .overlay import render_overlay
from .preview import render_data_preview
from .timeseries import plot_timeseries

__all__ = [
    "plot_timeseries",
    "build_file_batch_view",
    "render_data_preview",
    "render_bundle_algorithm_leaderboard",
    "render_bundle_file_matrix",
    "render_bundle_heatmap",
    "render_heatmap",
    "render_leaderboard",
    "render_overlay",
]
