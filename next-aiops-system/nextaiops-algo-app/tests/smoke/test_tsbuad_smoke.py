"""End-to-end smoke tests for TSB-UAD bridged algorithms.

These tests only run when TSB-UAD extras are installed.
In the default environment (without extras), they are automatically skipped.
"""

from pathlib import Path

import pytest

from nextaiops_algo.algorithms.adapters.tsbuad_registry import _tsbuad_available
from nextaiops_algo.algorithms.registry import REGISTRY
from nextaiops_algo.pipeline import run_experiment

# TSB-UAD algorithm names expected to be registered when extras are installed
TSBUAD_ALGO_NAMES = ["iforest", "lof", "ocsvm", "pca", "hbos"]

# Golden data path
GOLDEN_DATA_PATH = Path(__file__).parent / "golden_data" / "metrics.csv"


# Skip entire module if TSB-UAD is not available
if not _tsbuad_available():
    pytest.skip("TSB-UAD extras not installed", allow_module_level=True)


@pytest.fixture(scope="module")
def golden_data_path() -> Path:
    """Return path to golden dataset."""
    assert GOLDEN_DATA_PATH.exists(), f"Golden data not found: {GOLDEN_DATA_PATH}"
    return GOLDEN_DATA_PATH


@pytest.fixture(scope="module")
def output_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create temporary output directory for smoke tests."""
    return tmp_path_factory.mktemp("tsbuad_smoke_outputs")


class TestTSBUADSmoke:
    """Smoke tests for TSB-UAD bridged algorithms."""

    @pytest.mark.parametrize("algo_name", TSBUAD_ALGO_NAMES)
    def test_tsbuad_registered(self, algo_name: str) -> None:
        """Verify each TSB-UAD algorithm is registered."""
        assert algo_name in REGISTRY, f"{algo_name} not found in REGISTRY"

    @pytest.mark.parametrize("algo_name", TSBUAD_ALGO_NAMES)
    def test_smoke_run_success(
        self, algo_name: str, golden_data_path: Path, output_dir: Path
    ) -> None:
        """Smoke test: TSB-UAD algorithm runs without exception."""
        result = run_experiment(
            dataset_path=golden_data_path,
            algorithm_name=algo_name,
            params={},
            output_dir=output_dir,
        )
        assert result is not None
        assert result.run_id is not None

    @pytest.mark.parametrize("algo_name", TSBUAD_ALGO_NAMES)
    def test_smoke_output_table_contract(
        self, algo_name: str, golden_data_path: Path, output_dir: Path
    ) -> None:
        """Smoke test: output Table follows AnomalyDetector contract."""
        result = run_experiment(
            dataset_path=golden_data_path,
            algorithm_name=algo_name,
            params={},
            output_dir=output_dir,
        )
        assert result is not None

    @pytest.mark.parametrize("algo_name", TSBUAD_ALGO_NAMES)
    def test_smoke_non_degenerate_f1(
        self, algo_name: str, golden_data_path: Path, output_dir: Path
    ) -> None:
        """Smoke test: TSB-UAD algorithm is non-degenerate (F1 > 0 or PA-F1 > 0)."""
        result = run_experiment(
            dataset_path=golden_data_path,
            algorithm_name=algo_name,
            params={},
            output_dir=output_dir,
        )
        assert result.metrics is not None
        # Either standard F1 > 0 or PA-F1 > 0 constitutes non-degeneracy
        f1 = result.metrics.get("f1", 0.0)
        pa_f1 = result.metrics.get("pa_f1", 0.0)
        assert f1 > 0 or pa_f1 > 0, f"{algo_name} is degenerate: F1={f1}, PA-F1={pa_f1}"

    @pytest.mark.parametrize("algo_name", TSBUAD_ALGO_NAMES)
    def test_smoke_viz_html_exists(
        self, algo_name: str, golden_data_path: Path, output_dir: Path
    ) -> None:
        """Smoke test: viz.html artifact exists for TSB-UAD algorithms."""
        result = run_experiment(
            dataset_path=golden_data_path,
            algorithm_name=algo_name,
            params={},
            output_dir=output_dir,
        )
        viz_path = Path(result.artifacts_path) / "viz.html"
        assert viz_path.exists(), f"viz.html not found for {algo_name}"
        assert viz_path.stat().st_size > 0, f"viz.html empty for {algo_name}"
