"""Tests for TSB-UAD import guard - verifying graceful behavior without optional dependency."""


import pytest

from nextaiops_algo.algorithms.registry import REGISTRY


class TestTSBUADImportGuard:
    """Verify that TSB-UAD algorithms are NOT registered when the package is unavailable."""

    BASE_ALGO_NAMES = {"three_sigma", "iqr"}
    TSBUAD_ALGO_NAMES = {"iforest", "lof", "ocsvm", "pca", "hbos"}

    def test_no_tsbuad_in_registry_without_extras(self) -> None:
        """When TSB-UAD is not installed, REGISTRY should only contain base algorithms."""
        registered_names = set(REGISTRY.keys())
        # Base algorithms must always be present
        assert self.BASE_ALGO_NAMES.issubset(registered_names)
        # TSB-UAD algorithms must NOT be present (unless extras installed)
        # This test passes in default env (no extras) and is skipped in extras env
        tsbuad_overlap = registered_names & self.TSBUAD_ALGO_NAMES
        if tsbuad_overlap:
            pytest.skip(
                f"TSB-UAD extras installed: found {tsbuad_overlap}. "
                "This test verifies behavior WITHOUT extras."
            )
        # Confirm: no TSB-UAD names registered
        assert tsbuad_overlap == set()

    def test_import_adapters_module_without_tsbuad(self) -> None:
        """Importing adapters module should not raise ImportError without TSB-UAD."""
        from nextaiops_algo.algorithms.adapters import tsbuad_registry  # noqa: F401

        # Module imported successfully
        assert tsbuad_registry is not None

    def test_register_tsbuad_returns_empty_without_extras(self) -> None:
        """register_tsbuad_algorithms() returns empty list when TSB-UAD unavailable."""
        from nextaiops_algo.algorithms.adapters.tsbuad_registry import (
            _tsbuad_available,
            register_tsbuad_algorithms,
        )

        if _tsbuad_available():
            pytest.skip("TSB-UAD extras installed; this test verifies behavior WITHOUT extras.")
        result = register_tsbuad_algorithms()
        assert result == []

    def test_tsbuad_available_returns_bool(self) -> None:
        """_tsbuad_available() returns a boolean, never raises."""
        from nextaiops_algo.algorithms.adapters.tsbuad_registry import _tsbuad_available

        result = _tsbuad_available()
        assert isinstance(result, bool)

    def test_algorithms_init_importable_without_tsbuad(self) -> None:
        """algorithms/__init__.py can be imported without TSB-UAD extras."""
        # Re-import to verify no ImportError
        import nextaiops_algo.algorithms  # noqa: F401

        assert "REGISTRY" in dir(nextaiops_algo.algorithms)

    def test_tsbuad_adapter_class_importable_without_tsbuad(self) -> None:
        """TSBUADAdapter class itself can be imported (it's not a TSB-UAD dependency)."""
        from nextaiops_algo.algorithms.adapters.tsbuad_adapter import TSBUADAdapter

        assert TSBUADAdapter is not None
