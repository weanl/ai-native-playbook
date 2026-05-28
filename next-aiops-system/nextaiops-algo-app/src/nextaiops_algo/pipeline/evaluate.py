"""Evaluation metrics calculation for anomaly detection."""

import numpy as np

from nextaiops_algo.core.exceptions import SchemaValidationError
from nextaiops_algo.core.table import FieldRole, Table
from nextaiops_algo.pipeline.profile import anomaly_segments


def _compute_iou(seg_a: tuple[int, int], seg_b: tuple[int, int]) -> float:
    """Compute Intersection over Union (IoU) between two segments.

    Args:
        seg_a: (start, end) inclusive index range
        seg_b: (start, end) inclusive index range

    Returns:
        IoU value in [0, 1]
    """
    a_start, a_end = seg_a
    b_start, b_end = seg_b

    intersection = max(0, min(a_end, b_end) - max(a_start, b_start) + 1)
    if intersection == 0:
        return 0.0

    union = (a_end - a_start + 1) + (b_end - b_start + 1) - intersection
    return intersection / union if union > 0 else 0.0


def _segment_match_count(
    segments_ref: list[tuple[int, int]],
    segments_query: list[tuple[int, int]],
    iou_threshold: float,
) -> int:
    """Count how many ref segments match at least one query segment (IoU >= threshold).

    Args:
        segments_ref: Reference segments to check
        segments_query: Query segments to match against
        iou_threshold: Minimum IoU to count as a match

    Returns:
        Number of ref segments that have at least one match
    """
    matched = 0
    for ref_seg in segments_ref:
        if any(_compute_iou(ref_seg, q_seg) >= iou_threshold for q_seg in segments_query):
            matched += 1
    return matched


def point_adjust_labels(
    y_true: "np.ndarray[tuple[int], np.dtype[np.intp]]",
    y_pred: "np.ndarray[tuple[int], np.dtype[np.intp]]",
) -> "np.ndarray[tuple[int], np.dtype[np.intp]]":
    """Apply point-adjust to true labels based on prediction hits.

    For each contiguous anomaly segment (y_true=1 run), if y_pred hits
    any point in that segment, all points in that segment become TP (1).
    Unhit segments remain FN (original y_true=1). FP stays point-wise.

    Args:
        y_true: Ground truth labels (0/1 array).
        y_pred: Predicted labels (0/1 array).

    Returns:
        Adjusted y_true where hit segments are kept as 1,
        unhit segments become 0 for FN counting purposes.
    """
    adjusted = y_true.copy()
    n = len(y_true)
    i = 0
    while i < n:
        if y_true[i] == 1:
            # Find end of contiguous anomaly segment
            j = i
            while j < n and y_true[j] == 1:
                j += 1
            # Check if prediction hits any point in segment [i, j)
            segment_hit = np.any(y_pred[i:j] == 1)
            if not segment_hit:
                # Unhit segment: mark as 0 so FN counting works
                adjusted[i:j] = 0
            i = j
        else:
            i += 1
    return adjusted


def evaluate(
    input_table: Table,
    output_table: Table,
    segment_iou_threshold: float = 0.5,
) -> dict[str, float]:
    """Calculate precision, recall, F1 and Point-Adjust variants.

    Returns 8 metrics:
    - precision, recall, f1 (standard point-wise)
    - pa_precision, pa_recall, pa_f1 (point-adjust variants)
    - seg_recall, seg_precision (segment-level with IoU threshold)

    Args:
        input_table: Original input Table containing true labels.
        output_table: Algorithm output Table containing predicted labels.
        segment_iou_threshold: Minimum IoU to consider two segments as matched (default 0.5).

    Returns:
        Dict with 8 keys: precision, recall, f1, pa_precision, pa_recall, pa_f1,
        seg_recall, seg_precision.

    Raises:
        SchemaValidationError: If no LABEL in input or no predicted_label in output.
    """
    # Fail-fast: check for required columns
    if "predicted_label" not in output_table.df.columns:
        raise SchemaValidationError(
            "output_table missing required 'predicted_label' column",
            context={"output_columns": list(output_table.df.columns)},
        )

    y_true = input_table.labels()
    if y_true is None:
        raise SchemaValidationError(
            "input_table has no LABEL column — evaluation requires ground truth",
            context={"input_columns": list(input_table.df.columns)},
        )

    y_pred = output_table.df["predicted_label"]

    # Align by timestamp if both tables have it
    in_ts = input_table.timestamps()
    out_ts = output_table.timestamps()
    if in_ts is not None and out_ts is not None:
        y_true_aligned = input_table.df.set_index(
            input_table.schema.columns_of(FieldRole.TIMESTAMP)[0]
        )[input_table.schema.columns_of(FieldRole.LABEL)[0]]
        y_pred_aligned = output_table.df.set_index(
            output_table.schema.columns_of(FieldRole.TIMESTAMP)[0]
        )["predicted_label"]
        common_ts = y_true_aligned.index.intersection(y_pred_aligned.index)
        y_true = y_true_aligned.loc[common_ts]
        y_pred = y_pred_aligned.loc[common_ts]

    # Convert to numpy for PA calculation
    y_true_np = y_true.to_numpy(dtype=int)
    y_pred_np = y_pred.to_numpy(dtype=int)

    # Standard metrics (point-wise)
    tp = int(((y_true_np == 1) & (y_pred_np == 1)).sum())
    fp = int(((y_true_np == 0) & (y_pred_np == 1)).sum())
    fn = int(((y_true_np == 1) & (y_pred_np == 0)).sum())

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # Point-Adjust metrics (segment-level counting)
    pa_tp, pa_fn = 0, 0
    n = len(y_true_np)
    i = 0
    while i < n:
        if y_true_np[i] == 1:
            j = i
            while j < n and y_true_np[j] == 1:
                j += 1
            segment_len = j - i
            if np.any(y_pred_np[i:j] == 1):
                pa_tp += segment_len  # Hit: entire segment is TP
            else:
                pa_fn += segment_len  # Unhit: entire segment is FN
            i = j
        else:
            i += 1
    # FP is point-wise: y_true=0 AND y_pred=1
    pa_fp = int(((y_true_np == 0) & (y_pred_np == 1)).sum())

    pa_precision = pa_tp / (pa_tp + pa_fp) if (pa_tp + pa_fp) > 0 else 0.0
    pa_recall = pa_tp / (pa_tp + pa_fn) if (pa_tp + pa_fn) > 0 else 0.0
    pa_f1 = (
        2 * pa_precision * pa_recall / (pa_precision + pa_recall)
        if (pa_precision + pa_recall) > 0
        else 0.0
    )

    # Segment-level metrics (IoU-based)
    true_segments = anomaly_segments(y_true_np.tolist())
    pred_segments = anomaly_segments(y_pred_np.tolist())

    seg_recall = (
        _segment_match_count(true_segments, pred_segments, segment_iou_threshold) / len(true_segments)
        if len(true_segments) > 0
        else 0.0
    )
    seg_precision = (
        _segment_match_count(pred_segments, true_segments, segment_iou_threshold) / len(pred_segments)
        if len(pred_segments) > 0
        else 0.0
    )

    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "pa_precision": float(pa_precision),
        "pa_recall": float(pa_recall),
        "pa_f1": float(pa_f1),
        "seg_recall": float(seg_recall),
        "seg_precision": float(seg_precision),
    }
