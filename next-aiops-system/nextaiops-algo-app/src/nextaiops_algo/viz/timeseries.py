"""Time-series visualization with anomaly markers using Plotly."""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from nextaiops_algo.core.table import FieldRole, Table


def plot_timeseries(table: Table, output_path: Path | None = None) -> str:
    """Plot time-series with anomaly markers and thresholds.

    Creates a Plotly HTML visualization with:
    - Multiple subplots for each METRIC column
    - Original metric line (blue)
    - Upper/lower threshold lines (if present)
    - Anomaly points marked (red circles)
    - Graceful degradation for missing columns

    Args:
        table: Output Table from anomaly detection algorithm.
        output_path: Optional path to save HTML file. If None, returns HTML string.

    Returns:
        HTML string of the visualization.
    """
    metric_cols = table.schema.columns_of(FieldRole.METRIC)

    # Filter to only original metric columns (not derived .anomaly_score etc)
    original_metrics = [col for col in metric_cols if "." not in col]

    if len(original_metrics) == 0:
        original_metrics = metric_cols  # Fallback if naming convention not followed

    timestamps = table.timestamps()
    timestamps_series = timestamps if timestamps is not None else pd.Series(range(len(table.df)))
    x_values = timestamps_series.reset_index(drop=True)

    # Create subplots - one per original metric
    fig = make_subplots(
        rows=len(original_metrics),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=original_metrics,
    )

    for i, metric in enumerate(original_metrics):
        row = i + 1

        # Original metric line
        y_values = table.df[metric].reset_index(drop=True)
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=y_values,
                mode="lines",
                name=metric,
                line={"color": "blue"},
            ),
            row=row,
            col=1,
        )

        # Threshold lines (if present)
        upper_col = f"{metric}.threshold_upper"
        lower_col = f"{metric}.threshold_lower"

        if upper_col in table.df.columns:
            fig.add_trace(
                go.Scatter(
                    x=x_values,
                    y=table.df[upper_col].reset_index(drop=True),
                    mode="lines",
                    name=f"{metric} upper",
                    line={"color": "green", "dash": "dash"},
                ),
                row=row,
                col=1,
            )

        if lower_col in table.df.columns:
            fig.add_trace(
                go.Scatter(
                    x=x_values,
                    y=table.df[lower_col].reset_index(drop=True),
                    mode="lines",
                    name=f"{metric} lower",
                    line={"color": "green", "dash": "dash"},
                ),
                row=row,
                col=1,
            )

        # Anomaly markers (from predicted_label)
        if "predicted_label" in table.df.columns:
            predicted = table.df["predicted_label"].reset_index(drop=True)
            anomaly_mask = predicted == 1

            if anomaly_mask.any():
                fig.add_trace(
                    go.Scatter(
                        x=x_values[anomaly_mask],
                        y=y_values[anomaly_mask],
                        mode="markers",
                        name="Anomaly",
                        marker={"color": "red", "size": 10, "symbol": "circle"},
                    ),
                    row=row,
                    col=1,
                )

    # Update layout
    fig.update_layout(
        height=300 * len(original_metrics),
        title_text="Time Series Anomaly Detection",
        showlegend=True,
    )

    # Update x-axis labels
    x_axis_title = "Timestamp" if timestamps is not None else "Index"
    fig.update_xaxes(title_text=x_axis_title)

    html: str = fig.to_html(include_plotlyjs=True)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html)

    return html
