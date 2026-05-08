"""Unit tests for SqliteTrackingStore."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from nextaiops_algo.core.experiment import ExperimentRun, RunStatus
from nextaiops_algo.storage.sqlite_tracking import SqliteTrackingStore


class TestSqliteTrackingStore:
    """Tests for SqliteTrackingStore."""

    def test_round_trip_preserves_all_fields(self) -> None:
        """Test log_run → get_run preserves all fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SqliteTrackingStore(db_path=Path(tmpdir) / "test.db")

            run = ExperimentRun(
                run_id="test-run-001",
                dataset_version="v1",
                algorithm_name="three_sigma",
                params={"sigma": 3, "window": 10},
                status=RunStatus.COMPLETED,
                artifacts_path="/tmp/artifacts/test-run-001",
                created_at=datetime(2024, 1, 1, 12, 0, 0),
            )

            store.log_run(run)
            retrieved = store.get_run("test-run-001")

            assert retrieved is not None
            assert retrieved.run_id == run.run_id
            assert retrieved.dataset_version == run.dataset_version
            assert retrieved.algorithm_name == run.algorithm_name
            assert retrieved.params == run.params
            assert retrieved.status == run.status
            assert retrieved.artifacts_path == run.artifacts_path
            assert retrieved.created_at == run.created_at

    def test_get_run_returns_none_for_missing_id(self) -> None:
        """Test get_run returns None for non-existent run_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SqliteTrackingStore(db_path=Path(tmpdir) / "test.db")

            retrieved = store.get_run("nonexistent")
            assert retrieved is None

    def test_list_runs_returns_empty_when_none_logged(self) -> None:
        """Test list_runs returns empty list when no runs logged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SqliteTrackingStore(db_path=Path(tmpdir) / "test.db")

            runs = store.list_runs()
            assert runs == []

    def test_list_runs_orders_by_created_at_desc(self) -> None:
        """Test list_runs returns runs ordered by created_at descending."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SqliteTrackingStore(db_path=Path(tmpdir) / "test.db")

            run1 = ExperimentRun(
                run_id="run-001",
                dataset_version="v1",
                algorithm_name="algo",
                params={},
                status=RunStatus.COMPLETED,
                artifacts_path="/tmp/a",
                created_at=datetime(2024, 1, 1, 10, 0, 0),
            )

            run2 = ExperimentRun(
                run_id="run-002",
                dataset_version="v1",
                algorithm_name="algo",
                params={},
                status=RunStatus.COMPLETED,
                artifacts_path="/tmp/b",
                created_at=datetime(2024, 1, 1, 12, 0, 0),
            )

            store.log_run(run1)
            store.log_run(run2)

            runs = store.list_runs()
            assert len(runs) == 2
            assert runs[0].run_id == "run-002"  # newest first
            assert runs[1].run_id == "run-001"

    def test_list_runs_respects_limit(self) -> None:
        """Test list_runs respects limit parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SqliteTrackingStore(db_path=Path(tmpdir) / "test.db")

            for i in range(5):
                run = ExperimentRun(
                    run_id=f"run-{i}",
                    dataset_version="v1",
                    algorithm_name="algo",
                    params={},
                    status=RunStatus.COMPLETED,
                    artifacts_path="/tmp/a",
                    created_at=datetime(2024, 1, 1, 10 + i, 0, 0),
                )
                store.log_run(run)

            runs = store.list_runs(limit=3)
            assert len(runs) == 3

    def test_log_and_get_metrics(self) -> None:
        """Test log_metric and get_metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SqliteTrackingStore(db_path=Path(tmpdir) / "test.db")

            # First log a run so metrics FK can reference it
            run = ExperimentRun(
                run_id="run-001",
                dataset_version="v1",
                algorithm_name="algo",
                params={},
                status=RunStatus.COMPLETED,
                artifacts_path="/tmp/a",
                created_at=datetime(2024, 1, 1, 10, 0, 0),
            )
            store.log_run(run)

            store.log_metric("run-001", "precision", 0.85)
            store.log_metric("run-001", "recall", 0.90)
            store.log_metric("run-001", "f1", 0.87)

            metrics = store.get_metrics("run-001")
            assert metrics["precision"] == 0.85
            assert metrics["recall"] == 0.90
            assert metrics["f1"] == 0.87

    def test_get_metrics_returns_empty_for_missing_run(self) -> None:
        """Test get_metrics returns empty dict for non-existent run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SqliteTrackingStore(db_path=Path(tmpdir) / "test.db")

            metrics = store.get_metrics("nonexistent")
            assert metrics == {}