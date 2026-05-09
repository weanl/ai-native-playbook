"""Evaluation metrics calculation for anomaly detection."""

from nextaiops_algo.core.table import Table


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
