"""Unit tests for algorithm registry."""

from typing import ClassVar

import pytest

from nextaiops_algo.algorithms.params import AlgorithmParamSpec
from nextaiops_algo.algorithms.registry import (
    REGISTRY,
    create_algorithm,
    get_algorithm,
    get_algorithm_param_specs,
    list_algorithms,
    normalize_algorithm_params,
    register,
)
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

    def test_get_algorithm_param_specs_returns_declared_specs(self) -> None:
        """Parameter specs can be discovered from the registry."""

        class ParamAlgo(Algorithm):
            name = "test_algo_unique_param_specs"
            task_type = "task"
            required_input_roles = set()
            param_specs: ClassVar[tuple[AlgorithmParamSpec, ...]] = (
                AlgorithmParamSpec(name="k", type="float", default=3.0, description="k"),
            )

        register(ParamAlgo())

        specs = get_algorithm_param_specs("test_algo_unique_param_specs")

        assert len(specs) == 1
        assert specs[0].name == "k"

    def test_normalize_algorithm_params_uses_declared_specs(self) -> None:
        """Declared specs are used for param normalization."""

        class ParamAlgo(Algorithm):
            name = "test_algo_unique_normalize_params"
            task_type = "task"
            required_input_roles = set()
            param_specs: ClassVar[tuple[AlgorithmParamSpec, ...]] = (
                AlgorithmParamSpec(name="k", type="float", default=3.0, description="k"),
            )

        register(ParamAlgo())

        params = normalize_algorithm_params("test_algo_unique_normalize_params", {"k": "2"})

        assert params == {"k": 2.0}

    def test_create_algorithm_returns_fresh_parameterized_instance(self) -> None:
        """create_algorithm() constructs a fresh instance with normalized params."""

        class ParamAlgo(Algorithm):
            name = "test_algo_unique_create_params"
            task_type = "task"
            required_input_roles = set()
            param_specs: ClassVar[tuple[AlgorithmParamSpec, ...]] = (
                AlgorithmParamSpec(name="k", type="float", default=3.0, description="k"),
            )

            def __init__(self, k: float = 3.0) -> None:
                self.k = k

        registered = ParamAlgo()
        register(registered)

        created = create_algorithm("test_algo_unique_create_params", {"k": "2.5"})

        assert isinstance(created, ParamAlgo)
        assert created is not registered
        assert created.k == 2.5
