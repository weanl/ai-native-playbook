"""End-to-end smoke tests for all registered algorithms."""

from pathlib import Path

import pytest

from nextaiops_algo.algorithms.registry import REGISTRY
from nextaiops_algo.pipeline import run_experiment

# 黄金数据集路径
GOLDEN_DATA_PATH = Path(__file__).parent / "golden_data" / "metrics.csv"


@pytest.fixture(scope="module")
def golden_data_path() -> Path:
    """Return path to golden dataset."""
    assert GOLDEN_DATA_PATH.exists(), f"Golden data not found: {GOLDEN_DATA_PATH}"
    return GOLDEN_DATA_PATH


@pytest.fixture(scope="module")
def output_dir(tmp_path_factory) -> Path:
    """Create temporary output directory for smoke tests."""
    return tmp_path_factory.mktemp("smoke_outputs")


class TestE2ESmoke:
    """Smoke tests for all registered anomaly detection algorithms."""

    @pytest.mark.parametrize("algo_name", list(REGISTRY.keys()))
    def test_smoke_run_success(
        self, algo_name: str, golden_data_path: Path, output_dir: Path
    ) -> None:
        """Smoke test: algorithm runs without exception."""
        result = run_experiment(
            dataset_path=golden_data_path,
            algorithm_name=algo_name,
            params={},
            output_dir=output_dir,
        )
        assert result is not None
        assert result.run_id is not None

    @pytest.mark.parametrize("algo_name", list(REGISTRY.keys()))
    def test_smoke_viz_html_exists(
        self, algo_name: str, golden_data_path: Path, output_dir: Path
    ) -> None:
        """Smoke test: viz.html artifact exists and has content."""
        result = run_experiment(
            dataset_path=golden_data_path,
            algorithm_name=algo_name,
            params={},
            output_dir=output_dir,
        )
        viz_path = Path(result.artifacts_path) / "viz.html"
        assert viz_path.exists(), f"viz.html not found for {algo_name}"
        assert viz_path.stat().st_size > 0, f"viz.html empty for {algo_name}"
        # 检查包含 plotly 标记
        content = viz_path.read_text()
        assert "plotly-graph-div" in content, f"viz.html missing plotly marker for {algo_name}"

    @pytest.mark.parametrize("algo_name", list(REGISTRY.keys()))
    def test_smoke_persisted_to_db(
        self, algo_name: str, golden_data_path: Path, output_dir: Path
    ) -> None:
        """Smoke test: run persisted to SQLite tracking store."""
        from nextaiops_algo.storage.sqlite_tracking import SqliteTrackingStore

        result = run_experiment(
            dataset_path=golden_data_path,
            algorithm_name=algo_name,
            params={},
            output_dir=output_dir,
        )

        # 查询 SQLite
        store = SqliteTrackingStore()
        stored_run = store.get_run(result.run_id)
        assert stored_run is not None, f"Run {result.run_id} not found in SQLite"
        assert stored_run.algorithm_name == algo_name
        assert stored_run.status == "completed"

    @pytest.mark.parametrize("algo_name", list(REGISTRY.keys()))
    def test_smoke_f1_greater_than_zero(
        self, algo_name: str, golden_data_path: Path, output_dir: Path
    ) -> None:
        """Smoke test: algorithm is non-degenerate (F1 > 0)."""
        result = run_experiment(
            dataset_path=golden_data_path,
            algorithm_name=algo_name,
            params={},
            output_dir=output_dir,
        )
        assert result.metrics is not None
        assert "f1" in result.metrics
        assert result.metrics["f1"] > 0, f"{algo_name} F1={result.metrics['f1']} (退化)"
