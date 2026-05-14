"""Time-series visualization with anomaly markers using Plotly."""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from nextaiops_algo.core.table import FieldRole, Table
from nextaiops_algo.pipeline.profile import anomaly_segments

PLOTLY_INTERACTION_CONFIG: dict[str, object] = {
    "displaylogo": False,
    "scrollZoom": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
}


def plot_timeseries(
    table: Table,
    output_path: Path | None = None,
    input_table: Table | None = None,
) -> str:
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
        input_table: Optional evaluated input Table containing ground-truth labels.

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
    y_true = _aligned_true_labels(input_table, len(table.df))
    y_pred = _predicted_labels(table)

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
        score_col = f"{metric}.anomaly_score"
        score_values = (
            table.df[score_col].reset_index(drop=True)
            if score_col in table.df.columns
            else pd.Series([None] * len(table.df))
        )
        line_customdata = pd.DataFrame(
            {
                "score": score_values,
                "true": y_true if y_true is not None else pd.Series([None] * len(table.df)),
                "pred": y_pred if y_pred is not None else pd.Series([None] * len(table.df)),
            }
        )

        if y_true is not None:
            _add_ground_truth_bands(fig, x_values, y_true, row)

        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=y_values,
                mode="lines",
                name=metric,
                line={"color": "#2563eb", "width": 2},
                customdata=line_customdata,
                hovertemplate=(
                    "x=%{x}<br>"
                    "value=%{y:.4g}<br>"
                    "score=%{customdata[0]:.4g}<br>"
                    "true=%{customdata[1]}<br>"
                    "pred=%{customdata[2]}"
                    f"<extra>{metric}</extra>"
                ),
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
                    line={"color": "#059669", "dash": "dash", "width": 1.5},
                    hovertemplate="x=%{x}<br>upper=%{y:.4g}<extra>Upper threshold</extra>",
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
                    line={"color": "#059669", "dash": "dash", "width": 1.5},
                    hovertemplate="x=%{x}<br>lower=%{y:.4g}<extra>Lower threshold</extra>",
                ),
                row=row,
                col=1,
            )

        if y_true is not None and y_pred is not None:
            _add_classification_markers(fig, x_values, y_values, y_true, y_pred, row)
        elif y_pred is not None:
            _add_predicted_markers(fig, x_values, y_values, y_pred, row)

    # Update layout
    fig.update_layout(
        height=300 * len(original_metrics),
        title_text="Time Series Anomaly Detection",
        showlegend=True,
        hovermode="x unified",
        template="plotly_white",
        plot_bgcolor="#f8fafc",
        paper_bgcolor="#ffffff",
        margin={"l": 48, "r": 24, "t": 64, "b": 48},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )

    # Update x-axis labels
    x_axis_title = "Timestamp" if timestamps is not None else "Index"
    fig.update_xaxes(
        title_text=x_axis_title,
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikecolor="#64748b",
        spikethickness=1,
    )
    fig.update_yaxes(gridcolor="#e2e8f0")

    html: str = fig.to_html(include_plotlyjs=True, config=PLOTLY_INTERACTION_CONFIG)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html)

    return html


def _predicted_labels(table: Table) -> pd.Series | None:
    """Return predicted labels when present."""
    if "predicted_label" not in table.df.columns:
        return None
    return table.df["predicted_label"].reset_index(drop=True).fillna(0).astype(int)


def _aligned_true_labels(input_table: Table | None, expected_len: int) -> pd.Series | None:
    """Return true labels aligned by row when available."""
    if input_table is None:
        return None
    labels = input_table.labels()
    if labels is None or len(labels) != expected_len:
        return None
    return labels.reset_index(drop=True).fillna(0).astype(int)


def _add_ground_truth_bands(
    fig: go.Figure,
    x_values: pd.Series,
    y_true: pd.Series,
    row: int,
) -> None:
    """Add translucent bands for ground-truth anomaly segments."""
    for start, end in anomaly_segments(y_true.tolist()):
        fig.add_vrect(
            x0=x_values.iloc[start],
            x1=x_values.iloc[end],
            fillcolor="#64748b",
            opacity=0.12,
            line_width=0,
            layer="below",
            row=row,
            col=1,
        )


def _add_classification_markers(
    fig: go.Figure,
    x_values: pd.Series,
    y_values: pd.Series,
    y_true: pd.Series,
    y_pred: pd.Series,
    row: int,
) -> None:
    """Add TP/FP/FN markers."""
    masks = {
        "TP": (y_true == 1) & (y_pred == 1),
        "FP": (y_true == 0) & (y_pred == 1),
        "FN": (y_true == 1) & (y_pred == 0),
    }
    styles = {
        "TP": {"color": "#16a34a", "symbol": "circle", "size": 9},
        "FP": {"color": "#f97316", "symbol": "x", "size": 10},
        "FN": {"color": "#dc2626", "symbol": "diamond", "size": 9},
    }

    for label, mask in masks.items():
        if mask.any():
            fig.add_trace(
                go.Scatter(
                    x=x_values[mask],
                    y=y_values[mask],
                    mode="markers",
                    name=label,
                    marker=styles[label],
                    customdata=pd.DataFrame(
                        {
                            "true": y_true[mask].to_numpy(),
                            "pred": y_pred[mask].to_numpy(),
                        }
                    ),
                    hovertemplate=(
                        "x=%{x}<br>"
                        "value=%{y:.4g}<br>"
                        "true=%{customdata[0]}<br>"
                        "pred=%{customdata[1]}<br>"
                        f"class={label}<extra>{label}</extra>"
                    ),
                ),
                row=row,
                col=1,
            )


def _add_predicted_markers(
    fig: go.Figure,
    x_values: pd.Series,
    y_values: pd.Series,
    y_pred: pd.Series,
    row: int,
) -> None:
    """Add legacy predicted anomaly markers when true labels are unavailable."""
    anomaly_mask = y_pred == 1
    if anomaly_mask.any():
        fig.add_trace(
            go.Scatter(
                x=x_values[anomaly_mask],
                y=y_values[anomaly_mask],
                mode="markers",
                name="Anomaly",
                marker={"color": "#dc2626", "size": 10, "symbol": "circle"},
                hovertemplate="x=%{x}<br>value=%{y:.4g}<extra>Anomaly</extra>",
            ),
            row=row,
            col=1,
        )
