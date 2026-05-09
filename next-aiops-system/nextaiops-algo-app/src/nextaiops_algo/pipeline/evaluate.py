"""Evaluation metrics calculation for anomaly detection."""

from nextaiops_algo.core.table import FieldRole, Table


def evaluate(input_table: Table, output_table: Table) -> dict[str, float]:
    """Calculate precision, recall, and F1 for anomaly detection results.

    Evaluates based on the single `predicted_label` column in output_table
    against the `label` column in input_table (if present).

    M0 calculates global F1 based on OR-merged predicted_label.
    Per-metric evaluation (F1.<metric>) is deferred to M1.

    Args:
        input_table: Original input Table containing true labels.
        output_table: Algorithm output Table containing predicted labels.

    Returns:
        Dict with keys: "precision", "recall", "f1".
        Returns {"precision": 0.0, "recall": 0.0, "f1": 0.0} if no true labels.

    Raises:
        KeyError: If output_table lacks "predicted_label" column.
    """
    y_true = input_table.labels()
    y_pred = output_table.df["predicted_label"]

    if y_true is None:
        # No ground truth, return zeros
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    # Align by timestamp if both tables have it (PR-4 bug fix)
    in_ts = input_table.timestamps()
    out_ts = output_table.timestamps()
    if in_ts is not None and out_ts is not None:
        # Use timestamp to align
        y_true_aligned = input_table.df.set_index(
            input_table.schema.columns_of(FieldRole.TIMESTAMP)[0]
        )[input_table.schema.columns_of(FieldRole.LABEL)[0]]
        y_pred_aligned = output_table.df.set_index(
            output_table.schema.columns_of(FieldRole.TIMESTAMP)[0]
        )["predicted_label"]
        # Keep only common timestamps
        common_ts = y_true_aligned.index.intersection(y_pred_aligned.index)
        y_true = y_true_aligned.loc[common_ts]
        y_pred = y_pred_aligned.loc[common_ts]

    # Calculate true positives, false positives, false negatives
    tp = ((y_true == 1) & (y_pred == 1)).sum()
    fp = ((y_true == 0) & (y_pred == 1)).sum()
    fn = ((y_true == 1) & (y_pred == 0)).sum()

    # Precision: TP / (TP + FP)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0

    # Recall: TP / (TP + FN)
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    # F1: 2 * precision * recall / (precision + recall)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
    }
