"""Unit tests for algorithm registry."""

import pytest

from nextaiops_algo.algorithms.registry import REGISTRY, get_algorithm, list_algorithms, register
from nextaiops_algo.core.algorithm import Algorithm


class FakeAlgorithm(Algorithm):
    """Fake algorithm for testing."""

    name = "fake_algo_test"
    task_type = "fake_task"
    required_input_roles = set()


class TestRegistry:
    """Tests for algorithm registry."""

    def test_register_adds_to_registry(self) -> None:
        """Test register adds algorithm to REGISTRY."""
        # Use unique name to avoid conflicts with global registry
        class LocalFake(Algorithm):
            name = "test_algo_unique_001"
            task_type = "task"
            required_input_roles = set()

        algo = LocalFake()
        register(algo)

        assert "test_algo_unique_001" in REGISTRY
        assert REGISTRY["test_algo_unique_001"] == algo

    def test_register_returns_same_instance(self) -> None:
        """Test register returns the same algorithm instance."""
        class LocalFake(Algorithm):
            name = "test_algo_unique_002"
            task_type = "task"
            required_input_roles = set()

        algo = LocalFake()
        registered = register(algo)

        assert registered == algo

    def test_register_raises_on_duplicate_name(self) -> None:
        """Test register raises ValueError for duplicate name."""
        class LocalFake(Algorithm):
            name = "test_algo_unique_003"
            task_type = "task"
            required_input_roles = set()

        algo1 = LocalFake()
        register(algo1)

        algo2 = LocalFake()  # same name
        with pytest.raises(ValueError, match="already registered"):
            register(algo2)

    def test_get_algorithm_returns_registered_algo(self) -> None:
        """Test get_algorithm returns correct algorithm."""
        class LocalFake(Algorithm):
            name = "test_algo_unique_004"
            task_type = "task"
            required_input_roles = set()

        algo = LocalFake()
        register(algo)

        retrieved = get_algorithm("test_algo_unique_004")
        assert retrieved == algo

    def test_get_algorithm_returns_none_for_missing(self) -> None:
        """Test get_algorithm returns None for non-existent name."""
        retrieved = get_algorithm("nonexistent_algo_xyz")
        assert retrieved is None

    def test_list_algorithms_returns_sorted_names(self) -> None:
        """Test list_algorithms returns sorted list of names."""
        class AlgoTestA(Algorithm):
            name = "test_z_algo_a"
            task_type = "task"
            required_input_roles = set()

        class AlgoTestB(Algorithm):
            name = "test_z_algo_b"
            task_type = "task"
            required_input_roles = set()

        register(AlgoTestA())
        register(AlgoTestB())

        # Check these specific algos are in the list
        names = list_algorithms()
        assert "test_z_algo_a" in names
        assert "test_z_algo_b" in names

        # Check sorted order (these should appear in order)
        idx_a = names.index("test_z_algo_a")
        idx_b = names.index("test_z_algo_b")
        assert idx_a < idx_b