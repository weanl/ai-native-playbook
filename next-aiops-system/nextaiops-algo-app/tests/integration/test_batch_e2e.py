"""Integration tests for batch experiment e2e flow."""

from pathlib import Path

import pytest

from nextaiops_algo.algorithms.registry import REGISTRY
from nextaiops_algo.core.experiment import BatchStatus, RunStatus
from nextaiops_algo.pipeline.batch import run_batch

GOLDEN_DATA_PATH = Path(__file__).parent.parent / "smoke" / "golden_data" / "metrics.csv"


@pytest.fixture(scope="module")
def golden_data_path() -> Path:
    """Return path to golden dataset."""
    assert GOLDEN_DATA_PATH.exists(), f"Golden data not found: {GOLDEN_DATA_PATH}"
    return GOLDEN_DATA_PATH


@pytest.fixture(scope="module")
def output_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create temporary output directory."""
    return tmp_path_factory.mktemp("batch_outputs")


class TestBatchE2E:
    """End-to-end integration tests for batch experiments."""

    def test_batch_all_registered_algos(
        self, golden_data_path: Path, output_dir: Path
    ) -> None:
        """run_batch with all registered algorithms completes successfully."""
        batch = run_batch(
            dataset=golden_data_path,
            algorithms="__all__",
            output_dir=output_dir,
        )

        assert batch is not None
        assert batch.batch_id is not None
        assert len(batch.algorithm_names) == len(REGISTRY)
        assert batch.status in (BatchStatus.COMPLETED, BatchStatus.PARTIAL_FAILED)

    def test_batch_returns_run_for_each_algo(
        self, golden_data_path: Path, output_dir: Path
    ) -> None:
        """BatchRun contains ExperimentRun for each algorithm."""
        algo_names = ["three_sigma", "iqr"]
        batch = run_batch(
            dataset=golden_data_path,
            algorithms=algo_names,
            output_dir=output_dir,
        )

        assert len(batch.runs) == 2
        run_algo_names = [r.algorithm_name for r in batch.runs]
        assert "three_sigma" in run_algo_names
        assert "iqr" in run_algo_names

    def test_batch_successful_runs_have_metrics(
        self, golden_data_path: Path, output_dir: Path
    ) -> None:
        """Each completed run has full metrics dict."""
        batch = run_batch(
            dataset=golden_data_path,
            algorithms=["three_sigma"],
            output_dir=output_dir,
        )

        for run in batch.runs:
            if run.status == RunStatus.COMPLETED:
                # Metrics are stored in tracking store, not in ExperimentRun
                from nextaiops_algo.storage.sqlite_tracking import SqliteTrackingStore

                store = SqliteTrackingStore()
                metrics = store.get_metrics(run.run_id)
                assert "f1" in metrics
                assert "pa_f1" in metrics

    def test_batch_failed_algo_does_not_block(
        self, golden_data_path: Path, output_dir: Path
    ) -> None:
        """A failing algorithm does not block other algorithms in the batch."""
        batch = run_batch(
            dataset=golden_data_path,
            algorithms=["three_sigma", "nonexistent_algo", "iqr"],
            output_dir=output_dir,
        )

        # Batch should have partial failure
        assert batch.status == BatchStatus.PARTIAL_FAILED

        # At least one run completed
        completed_runs = [r for r in batch.runs if r.status == RunStatus.COMPLETED]
        assert len(completed_runs) >= 1

        # At least one run failed
        failed_runs = [r for r in batch.runs if r.status == RunStatus.FAILED]
        assert len(failed_runs) >= 1

    def test_batch_persisted_to_sqlite(
        self, golden_data_path: Path, output_dir: Path
    ) -> None:
        """Batch is persisted in SQLite and can be queried."""
        from nextaiops_algo.storage.sqlite_tracking import SqliteTrackingStore

        batch = run_batch(
            dataset=golden_data_path,
            algorithms=["three_sigma"],
            output_dir=output_dir,
        )

        store = SqliteTrackingStore()
        retrieved = store.get_batch(batch.batch_id)
        assert retrieved is not None
        assert retrieved.batch_id == batch.batch_id
        assert retrieved.dataset_source == str(golden_data_path)
        assert "three_sigma" in retrieved.algorithm_names

    def test_batch_cli_list_batches(
        self, golden_data_path: Path, output_dir: Path
    ) -> None:
        """list-batches returns the created batch."""
        from nextaiops_algo.storage.sqlite_tracking import SqliteTrackingStore

        batch = run_batch(
            dataset=golden_data_path,
            algorithms=["three_sigma"],
            output_dir=output_dir,
        )

        store = SqliteTrackingStore()
        batches = store.list_batches()
        assert len(batches) >= 1

        # Find our batch
        found = any(b.batch_id == batch.batch_id for b in batches)
        assert found
