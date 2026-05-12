"""Evaluation metrics calculation for anomaly detection."""

import numpy as np

from nextaiops_algo.core.exceptions import SchemaValidationError
from nextaiops_algo.core.table import FieldRole, Table


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


def evaluate(input_table: Table, output_table: Table) -> dict[str, float]:
    """Calculate precision, recall, F1 and Point-Adjust variants.

    Returns 6 metrics:
    - precision, recall, f1 (standard point-wise)
    - pa_precision, pa_recall, pa_f1 (point-adjust variants)

    Args:
        input_table: Original input Table containing true labels.
        output_table: Algorithm output Table containing predicted labels.

    Returns:
        Dict with 6 keys: precision, recall, f1, pa_precision, pa_recall, pa_f1.

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

    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "pa_precision": float(pa_precision),
        "pa_recall": float(pa_recall),
        "pa_f1": float(pa_f1),
    }
