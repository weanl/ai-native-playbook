"""Algorithm registry - central registration point for all algorithms."""

from typing import Any, TypeVar, cast

from nextaiops_algo.algorithms.params import AlgorithmParamSpec, normalize_params
from nextaiops_algo.core.algorithm import Algorithm

T = TypeVar("T", bound=Algorithm)

# Global registry of all registered algorithms
REGISTRY: dict[str, Algorithm] = {}


def register(algo: T | type[T]) -> T | type[T]:
    """Register an algorithm in the global REGISTRY.

    Can be used as a decorator on a class or on an instance.

    Args:
        algo: An algorithm instance or algorithm class implementing the Algorithm protocol.

    Returns:
        The same algorithm instance or class (for decorator chaining).

    Raises:
        ValueError: If algorithm name is already registered.

    Example:
        @register
        class ThreeSigma:
            name = "three_sigma"
            ...

        or:

        three_sigma = ThreeSigma()
        register(three_sigma)
    """
    # If algo is a class, instantiate it
    if isinstance(algo, type):
        instance = algo()
        if instance.name in REGISTRY:
            raise ValueError(f"Algorithm '{instance.name}' already registered")
        REGISTRY[instance.name] = instance
        return algo  # return class for decorator chaining
    else:
        # algo is an instance
        if algo.name in REGISTRY:
            raise ValueError(f"Algorithm '{algo.name}' already registered")
        REGISTRY[algo.name] = algo
        return algo


def get_algorithm(name: str) -> Algorithm | None:
    """Get an algorithm by name from the registry.

    Args:
        name: The algorithm name to look up.

    Returns:
        The algorithm instance if found, else None.
    """
    return REGISTRY.get(name)


def get_algorithm_param_specs(name: str) -> tuple[AlgorithmParamSpec, ...]:
    """Get parameter specs declared by an algorithm.

    Args:
        name: The algorithm name to look up.

    Returns:
        Tuple of parameter specs. Empty tuple means no metadata is declared.
    """
    algo = get_algorithm(name)
    if algo is None:
        return ()

    specs = getattr(algo, "param_specs", ())
    if isinstance(specs, tuple):
        return cast(tuple[AlgorithmParamSpec, ...], specs)
    return ()


def normalize_algorithm_params(name: str, params: dict[str, object] | None) -> dict[str, object]:
    """Normalize params for an algorithm using declared specs when available.

    Algorithms without declared specs keep their raw params unchanged so existing
    adapter-style algorithms can continue to accept JSON overrides.
    """
    specs = get_algorithm_param_specs(name)
    if not specs:
        return dict(params or {})
    return normalize_params(specs, params)


def create_algorithm(name: str, params: dict[str, object] | None = None) -> Algorithm | None:
    """Create a fresh algorithm instance for a run.

    Args:
        name: Algorithm name registered in REGISTRY.
        params: User supplied params. Declared params are normalized before
            constructor injection.

    Returns:
        A fresh algorithm instance when possible, or None if the name is unknown.

    Raises:
        ValueError: If params are invalid or the algorithm cannot be constructed
            with the supplied params.
    """
    registered = get_algorithm(name)
    if registered is None:
        return None

    normalized_params = normalize_algorithm_params(name, params)
    factory = getattr(registered, "with_params", None)
    if callable(factory):
        created = factory(normalized_params)
        return cast(Algorithm, created)

    algo_cls = cast(type[Any], registered.__class__)
    try:
        return cast(Algorithm, algo_cls(**normalized_params))
    except TypeError as exc:
        if normalized_params:
            raise ValueError(
                f"Algorithm '{name}' does not accept parameter(s): "
                f"{', '.join(sorted(normalized_params))}"
            ) from exc
        try:
            return cast(Algorithm, algo_cls())
        except TypeError:
            return registered


def list_algorithms() -> list[str]:
    """List all registered algorithm names.

    Returns:
        List of algorithm names in the registry.
    """
    return sorted(REGISTRY.keys())
