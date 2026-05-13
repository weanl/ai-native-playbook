"""Unit tests for leaderboard visualization."""

from datetime import datetime

import pandas as pd

from nextaiops_algo.core.experiment import BatchRun, BatchStatus, ExperimentRun, RunStatus
from nextaiops_algo.storage.sqlite_tracking import SqliteTrackingStore
from nextaiops_algo.viz.leaderboard import render_leaderboard


class TestRenderLeaderboard:
    """Tests for render_leaderboard function."""

    def _make_run(self, algo_name: str, status: RunStatus = RunStatus.COMPLETED) -> ExperimentRun:
        return ExperimentRun(
            run_id=f"run_{algo_name}",
            dataset_version="test_data",
            algorithm_name=algo_name,
            params={},
            status=status,
            artifacts_path="/tmp/test",
            created_at=datetime(2024, 1, 1, 12, 0),
        )

    def _make_batch_with_metrics(self, tmp_path: object) -> tuple[BatchRun, SqliteTrackingStore]:
        """Create a BatchRun with logged runs and metrics."""
        store = SqliteTrackingStore(db_path=tmp_path / "leaderboard.db")

        runs = [
            self._make_run("three_sigma"),
            self._make_run("iqr"),
        ]

        for run in runs:
            store.log_run(run)

        # Log metrics: iqr has higher PA-F1
        store.log_metric("run_three_sigma", "precision", 0.6)
        store.log_metric("run_three_sigma", "recall", 0.5)
        store.log_metric("run_three_sigma", "f1", 0.545)
        store.log_metric("run_three_sigma", "pa_precision", 0.7)
        store.log_metric("run_three_sigma", "pa_recall", 0.6)
        store.log_metric("run_three_sigma", "pa_f1", 0.646)

        store.log_metric("run_iqr", "precision", 0.8)
        store.log_metric("run_iqr", "recall", 0.7)
        store.log_metric("run_iqr", "f1", 0.747)
        store.log_metric("run_iqr", "pa_precision", 0.9)
        store.log_metric("run_iqr", "pa_recall", 0.8)
        store.log_metric("run_iqr", "pa_f1", 0.847)

        return BatchRun(
            batch_id="batch_test",
            dataset_source="test.csv",
            algorithm_names=["three_sigma", "iqr"],
            created_at=datetime(2024, 1, 1, 12, 0),
            runs=runs,
            status=BatchStatus.COMPLETED,
        ), store

    def test_leaderboard_row_count_equals_algorithm_count(self, tmp_path: object) -> None:
        """Leaderboard has rows equal to number of algorithms."""
        batch, store = self._make_batch_with_metrics(tmp_path)
        df = render_leaderboard(batch, store=store)

        assert len(df) == 2

    def test_leaderboard_sorted_by_pa_f1_descending(self, tmp_path: object) -> None:
        """Leaderboard is sorted by PA-F1 descending."""
        batch, store = self._make_batch_with_metrics(tmp_path)
        df = render_leaderboard(batch, store=store)

        assert df.iloc[0]["Algorithm"] == "iqr"
        assert df.iloc[1]["Algorithm"] == "three_sigma"

    def test_leaderboard_contains_metric_columns(self, tmp_path: object) -> None:
        """Leaderboard DataFrame has all expected metric columns."""
        batch, store = self._make_batch_with_metrics(tmp_path)
        df = render_leaderboard(batch, store=store)

        expected_cols = ["Algorithm", "Status", "Precision", "Recall", "F1", "PA-Precision", "PA-Recall", "PA-F1", "Error"]
        for col in expected_cols:
            assert col in df.columns

    def test_leaderboard_failed_run_has_nan_metrics(self, tmp_path: object) -> None:
        """Failed run shows NaN for all metric columns."""
        store = SqliteTrackingStore(db_path=tmp_path / "leaderboard_failed.db")

        completed_run = self._make_run("three_sigma")
        failed_run = ExperimentRun(
            run_id="run_bad",
            dataset_version="test_data",
            algorithm_name="bad_algo",
            params={},
            status=RunStatus.FAILED,
            artifacts_path="",
            created_at=datetime(2024, 1, 1, 12, 0),
        )

        store.log_run(completed_run)
        store.log_run(failed_run)
        store.log_metric("run_three_sigma", "pa_f1", 0.5)

        batch = BatchRun(
            batch_id="batch_failed",
            dataset_source="test.csv",
            algorithm_names=["three_sigma", "bad_algo"],
            created_at=datetime(2024, 1, 1, 12, 0),
            runs=[completed_run, failed_run],
            status=BatchStatus.PARTIAL_FAILED,
        )

        df = render_leaderboard(batch)

        bad_row = df[df["Algorithm"] == "bad_algo"]
        assert bad_row.iloc[0]["Status"] == "failed"
        assert pd.isna(bad_row.iloc[0]["PA-F1"])

    def test_leaderboard_custom_sort_by_f1(self, tmp_path: object) -> None:
        """Leaderboard can sort by a different metric column."""
        batch, store = self._make_batch_with_metrics(tmp_path)
        df = render_leaderboard(batch, sort_by="f1", store=store)

        # iqr has higher F1 too, so it's still first
        assert df.iloc[0]["Algorithm"] == "iqr"

    def test_leaderboard_failed_runs_at_bottom(self, tmp_path: object) -> None:
        """Failed runs are sorted to the bottom."""
        store = SqliteTrackingStore(db_path=tmp_path / "leaderboard_order.db")

        completed_run = self._make_run("iqr")
        failed_run = ExperimentRun(
            run_id="run_bad",
            dataset_version="test_data",
            algorithm_name="bad_algo",
            params={},
            status=RunStatus.FAILED,
            artifacts_path="",
            created_at=datetime(2024, 1, 1, 12, 0),
        )

        store.log_run(completed_run)
        store.log_run(failed_run)
        store.log_metric("run_iqr", "pa_f1", 0.5)

        batch = BatchRun(
            batch_id="batch_order",
            dataset_source="test.csv",
            algorithm_names=["iqr", "bad_algo"],
            created_at=datetime(2024, 1, 1, 12, 0),
            runs=[completed_run, failed_run],
            status=BatchStatus.PARTIAL_FAILED,
        )

        df = render_leaderboard(batch)

        # Completed run should be at top, failed at bottom
        assert df.iloc[-1]["Algorithm"] == "bad_algo"
