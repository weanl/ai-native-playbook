"""Algorithm registry - central registration point for all algorithms."""

from typing import TypeVar

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


def list_algorithms() -> list[str]:
    """List all registered algorithm names.

    Returns:
        List of algorithm names in the registry.
    """
    return sorted(REGISTRY.keys())
