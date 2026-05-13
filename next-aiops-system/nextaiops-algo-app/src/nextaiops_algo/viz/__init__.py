"""Viz module - Visualization layer.

This module provides visualization capabilities for NextAIOpsAlgoApp:
- timeseries: Time-series plots with anomaly markers
- leaderboard: Batch experiment ranked DataFrame
- overlay: Multi-algorithm detection overlay comparison
- heatmap: Algorithm × metrics matrix heatmap

Visualization outputs pure HTML files (Plotly), independent of web frameworks.
Graceful degradation for missing columns (timestamp, thresholds, scores).
"""

from .heatmap import render_heatmap
from .leaderboard import render_leaderboard
from .overlay import render_overlay
from .timeseries import plot_timeseries

__all__ = [
    "plot_timeseries",
    "render_heatmap",
    "render_leaderboard",
    "render_overlay",
]
