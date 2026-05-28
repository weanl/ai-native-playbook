"""Detection diagnostics for explaining anomaly experiment results."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from nextaiops_algo.core.exceptions import SchemaValidationError
from nextaiops_algo.core.table import Table
from nextaiops_algo.pipeline.evaluate import _segment_match_count
from nextaiops_algo.pipeline.profile import anomaly_segments


@dataclass(frozen=True)
class DetectionDiagnostics:
    """Point-wise and segment-wise explanation of detection results."""

    true_anomalies: int
    predicted_anomalies: int
    tp: int
    fp: int
    fn: int
    tn: int
    true_segments: int
    hit_segments: int
    predicted_segments: int
    seg_recall: float
    seg_precision: float

    def to_dict(self) -> dict[str, int | float]:
        """Return a JSON-serializable representation."""
        result = {}
        for key, value in asdict(self).items():
            if isinstance(value, float):
                result[key] = float(value)
            else:
                result[key] = int(value)
        return result


def diagnose_detection(
    input_table: Table,
    output_table: Table,
    segment_iou_threshold: float = 0.5,
) -> DetectionDiagnostics:
    """Compare ground-truth labels with predicted labels.

    Args:
        input_table: Input table for the evaluated split, containing LABEL.
        output_table: Algorithm output table, containing ``predicted_label``.
        segment_iou_threshold: Minimum IoU to consider two segments as matched (default 0.5).

    Returns:
        DetectionDiagnostics with point counts and segment hit counts.

    Raises:
        SchemaValidationError: If labels or predictions are missing, or lengths differ.
    """
    y_true_series = input_table.labels()
    if y_true_series is None:
        raise SchemaValidationError(
            "input_table has no LABEL column — diagnostics require ground truth",
            context={"input_columns": list(input_table.df.columns)},
        )

    if "predicted_label" not in output_table.df.columns:
        raise SchemaValidationError(
            "output_table missing required 'predicted_label' column",
            context={"output_columns": list(output_table.df.columns)},
        )

    if len(input_table.df) != len(output_table.df):
        raise SchemaValidationError(
            f"diagnostics row count mismatch: input={len(input_table.df)}, "
            f"output={len(output_table.df)}"
        )

    y_true = [int(value) for value in y_true_series.reset_index(drop=True).fillna(0).tolist()]
    y_pred = [
        int(value)
        for value in output_table.df["predicted_label"].reset_index(drop=True).fillna(0).tolist()
    ]

    tp = sum(1 for true, pred in zip(y_true, y_pred, strict=True) if true == 1 and pred == 1)
    fp = sum(1 for true, pred in zip(y_true, y_pred, strict=True) if true == 0 and pred == 1)
    fn = sum(1 for true, pred in zip(y_true, y_pred, strict=True) if true == 1 and pred == 0)
    tn = sum(1 for true, pred in zip(y_true, y_pred, strict=True) if true == 0 and pred == 0)

    segments = anomaly_segments(y_true)
    pred_segments = anomaly_segments(y_pred)
    hit_segments = sum(
        1 for start, end in segments if any(pred == 1 for pred in y_pred[start : end + 1])
    )

    # IoU-based segment matching
    seg_recall = (
        _segment_match_count(segments, pred_segments, segment_iou_threshold) / len(segments)
        if len(segments) > 0
        else 0.0
    )
    seg_precision = (
        _segment_match_count(pred_segments, segments, segment_iou_threshold) / len(pred_segments)
        if len(pred_segments) > 0
        else 0.0
    )

    return DetectionDiagnostics(
        true_anomalies=sum(1 for value in y_true if value == 1),
        predicted_anomalies=sum(1 for value in y_pred if value == 1),
        tp=tp,
        fp=fp,
        fn=fn,
        tn=tn,
        true_segments=len(segments),
        hit_segments=hit_segments,
        predicted_segments=len(pred_segments),
        seg_recall=seg_recall,
        seg_precision=seg_precision,
    )
