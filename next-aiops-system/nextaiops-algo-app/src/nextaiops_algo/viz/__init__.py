"""Viz module - Visualization layer.

This module provides visualization capabilities for NextAIOpsAlgoApp:
- timeseries: Time-series plots with anomaly markers

Visualization outputs pure HTML files (Plotly), independent of web frameworks.
Graceful degradation for missing columns (timestamp, thresholds, scores).
"""

from .timeseries import plot_timeseries

__all__ = [
    "plot_timeseries",
]
