"""Leaderboard visualization — render BatchRun results as a ranked DataFrame."""

import pandas as pd

from nextaiops_algo.core.experiment import BatchRun, RunStatus
from nextaiops_algo.storage.sqlite_tracking import SqliteTrackingStore

_METRIC_KEYS = [
    "precision",
    "recall",
    "f1",
    "pa_precision",
    "pa_recall",
    "pa_f1",
]

_DISPLAY_NAMES = {
    "precision": "Precision",
    "recall": "Recall",
    "f1": "F1",
    "pa_precision": "PA-Precision",
    "pa_recall": "PA-Recall",
    "pa_f1": "PA-F1",
}


def render_leaderboard(
    batch_run: BatchRun,
    sort_by: str = "pa_f1",
    store: SqliteTrackingStore | None = None,
) -> pd.DataFrame:
    """Render a BatchRun as a leaderboard DataFrame.

    Each row represents one algorithm run. Rows are sorted by the
    specified metric column (default: PA-F1 descending).

    FAILED runs are included with NaN metrics and marked in the
    Status column.

    Args:
        batch_run: The BatchRun containing per-algorithm ExperimentRun records.
        sort_by: Metric key to sort by (default "pa_f1").
        store: Optional SqliteTrackingStore instance. If None, creates default.

    Returns:
        DataFrame with columns: Algorithm, Status, and metric columns.
    """
    if store is None:
        store = SqliteTrackingStore()
    rows: list[dict[str, object]] = []

    for run in batch_run.runs:
        row: dict[str, object] = {
            "Algorithm": run.algorithm_name,
            "Status": run.status.value,
        }

        if run.status == RunStatus.COMPLETED:
            metrics = store.get_metrics(run.run_id)
            for key in _METRIC_KEYS:
                row[_DISPLAY_NAMES[key]] = metrics.get(key)
        else:
            for key in _METRIC_KEYS:
                row[_DISPLAY_NAMES[key]] = float("nan")

        row["Error"] = None
        rows.append(row)

    df = pd.DataFrame(rows)

    display_sort = _DISPLAY_NAMES.get(sort_by, sort_by)
    if display_sort in df.columns:
        df = df.sort_values(display_sort, ascending=False, na_position="last")

    return df
