"""Data preview visualization for input Tables."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from nextaiops_algo.core.table import FieldRole, Table
from nextaiops_algo.pipeline.profile import anomaly_segments


def render_data_preview(table: Table, metric_name: str | None = None) -> go.Figure:
    """Render an input data preview chart.

    The preview shows one metric curve and, when labels exist, overlays
    ground-truth anomaly markers plus translucent anomaly segment bands.

    Args:
        table: Input data table.
        metric_name: Optional metric column to render. Defaults to first metric.

    Returns:
        Plotly Figure suitable for Streamlit or HTML export.

    Raises:
        ValueError: If the requested metric does not exist.
    """
    metric_columns = table.schema.columns_of(FieldRole.METRIC)
    if not metric_columns:
        raise ValueError("Table has no METRIC columns to preview")

    selected_metric = metric_name or metric_columns[0]
    if selected_metric not in metric_columns:
        raise ValueError(f"Unknown metric column: {selected_metric}")

    timestamps = table.timestamps()
    x_values = (
        timestamps.reset_index(drop=True)
        if timestamps is not None
        else pd.Series(range(len(table.df)))
    )
    y_values = table.df[selected_metric].reset_index(drop=True)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=y_values,
            mode="lines",
            name=selected_metric,
            line={"color": "#2563eb", "width": 2},
            hovertemplate=(
                f"x=%{{x}}<br>{selected_metric}=%{{y:.4g}}<extra>{selected_metric}</extra>"
            ),
        )
    )

    labels = table.labels()
    if labels is not None:
        label_values = labels.reset_index(drop=True).fillna(0).astype(int)
        anomaly_mask = label_values == 1
        _add_anomaly_bands(fig, x_values, label_values.tolist())

        if anomaly_mask.any():
            fig.add_trace(
                go.Scatter(
                    x=x_values[anomaly_mask],
                    y=y_values[anomaly_mask],
                    mode="markers",
                    name="Ground Truth",
                    marker={"color": "#dc2626", "size": 8, "symbol": "diamond"},
                    customdata=label_values[anomaly_mask],
                    hovertemplate=(
                        "x=%{x}<br>"
                        f"{selected_metric}=%{{y:.4g}}<br>"
                        "label=%{customdata}<extra>Ground Truth</extra>"
                    ),
                )
            )

    fig.update_layout(
        title=f"Data Preview: {selected_metric}",
        height=420,
        margin={"l": 40, "r": 24, "t": 56, "b": 40},
        hovermode="x unified",
        template="plotly_white",
        plot_bgcolor="#f8fafc",
        paper_bgcolor="#ffffff",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    fig.update_xaxes(title_text="Timestamp" if timestamps is not None else "Index", showspikes=True)
    fig.update_yaxes(title_text=selected_metric, gridcolor="#e2e8f0")

    return fig


def _add_anomaly_bands(fig: go.Figure, x_values: pd.Series, labels: list[int]) -> None:
    """Add translucent vertical bands for labeled anomaly segments."""
    for start, end in anomaly_segments(labels):
        fig.add_vrect(
            x0=x_values.iloc[start],
            x1=x_values.iloc[end],
            fillcolor="#dc2626",
            opacity=0.12,
            line_width=0,
            layer="below",
        )
