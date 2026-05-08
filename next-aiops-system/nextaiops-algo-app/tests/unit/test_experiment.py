"""Unit tests for ExperimentRun and RunResult."""

from datetime import datetime

from nextaiops_algo.core import ExperimentRun, RunResult, RunStatus


class TestExperimentRun:
    """Tests for ExperimentRun data model."""

    def test_experiment_run_all_fields_present(self) -> None:
        """ExperimentRun has all required fields."""
        now = datetime.now()
        run = ExperimentRun(
            run_id="test-run-001",
            dataset_version="v1",
            algorithm_name="three_sigma",
            params={"threshold": 3.0},
            status=RunStatus.COMPLETED,
            artifacts_path="/path/to/artifacts",
            created_at=now,
        )
        assert run.run_id == "test-run-001"
        assert run.dataset_version == "v1"
        assert run.algorithm_name == "three_sigma"
        assert run.params == {"threshold": 3.0}
        assert run.status == RunStatus.COMPLETED
        assert run.artifacts_path == "/path/to/artifacts"
        assert run.created_at == now

    def test_experiment_run_status_values(self) -> None:
        """RunStatus enum has all expected values."""
        assert RunStatus.RUNNING == "running"
        assert RunStatus.COMPLETED == "completed"
        assert RunStatus.FAILED == "failed"

    def test_experiment_run_params_is_dict(self) -> None:
        """ExperimentRun.params is a dict[str, Any] with flexible structure."""
        run = ExperimentRun(
            run_id="test-run-002",
            dataset_version="v1",
            algorithm_name="test_algo",
            params={"nested": {"key": "value"}, "list": [1, 2, 3]},
            status=RunStatus.RUNNING,
            artifacts_path="/path",
            created_at=datetime.now(),
        )
        assert run.params["nested"]["key"] == "value"
        assert run.params["list"] == [1, 2, 3]


class TestRunResult:
    """Tests for RunResult data model."""

    def test_run_result_all_fields_present(self) -> None:
        """RunResult has all required fields."""
        result = RunResult(
            run_id="test-run-001",
            metrics={"precision": 0.8, "recall": 0.75, "f1": 0.77},
            artifacts_path="/path/to/artifacts",
        )
        assert result.run_id == "test-run-001"
        assert result.metrics["precision"] == 0.8
        assert result.metrics["recall"] == 0.75
        assert result.metrics["f1"] == 0.77
        assert result.artifacts_path == "/path/to/artifacts"

    def test_run_result_metrics_is_dict(self) -> None:
        """RunResult.metrics is a dict[str, float]."""
        result = RunResult(
            run_id="test-run-003",
            metrics={"custom_metric": 0.123},
            artifacts_path="/path",
        )
        assert result.metrics["custom_metric"] == 0.123
