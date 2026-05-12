"""Dataset registry for builtin datasets."""

from typing import Protocol, runtime_checkable

from nextaiops_algo.core.table import Table


@runtime_checkable
class BuiltinDataset(Protocol):
    """Protocol for builtin datasets packaged in the wheel."""

    name: str
    description: str
    n_points: int
    source: str

    def load(self) -> Table:
        """Load the builtin dataset into a Table."""
        ...


def list_builtin() -> list[str]:
    """Return names of all available builtin datasets."""
    return sorted(BUILTIN_REGISTRY.keys())


def get_builtin(name: str) -> BuiltinDataset:
    """Get a builtin dataset by name.

    Args:
        name: Dataset name (e.g. 'yahoo_sample').

    Returns:
        BuiltinDataset instance.

    Raises:
        KeyError: If name not found in registry.
    """
    if name not in BUILTIN_REGISTRY:
        available = list_builtin()
        raise KeyError(
            f"Unknown builtin dataset '{name}'. Available: {available}"
        )
    return BUILTIN_REGISTRY[name]


# Registry populated by builtin dataset modules on import
BUILTIN_REGISTRY: dict[str, BuiltinDataset] = {}
