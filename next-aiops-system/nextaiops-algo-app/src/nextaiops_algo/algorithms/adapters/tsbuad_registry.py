"""TSB-UAD conditional registration - dynamically registers algorithms when TSB-UAD is available.

This module attempts to import TSB-UAD and register all configured algorithms
into the global REGISTRY. If TSB-UAD is not installed, registration is silently
skipped without raising ImportError.
"""

from __future__ import annotations

from nextaiops_algo.algorithms.adapters.tsbuad_adapter import TSBUADAdapter
from nextaiops_algo.algorithms.adapters.tsbuad_configs import TSBUAD_ALGO_CONFIGS
from nextaiops_algo.algorithms.registry import REGISTRY


def _tsbuad_available() -> bool:
    """Check whether TSB-UAD package is importable.

    Returns:
        True if TSB_UAD can be imported, False otherwise.
    """
    try:
        import TSB_UAD  # noqa: F401

        return True
    except ImportError:
        return False


def register_tsbuad_algorithms() -> list[str]:
    """Register all TSB-UAD algorithms into the global REGISTRY if available.

    When TSB-UAD is installed, creates TSBUADAdapter instances for each configured
    algorithm and adds them to REGISTRY. When not installed, returns an empty list
    and does not raise any error.

    Returns:
        List of algorithm names that were successfully registered.
    """
    if not _tsbuad_available():
        return []

    registered: list[str] = []
    for name, config in TSBUAD_ALGO_CONFIGS.items():
        if name in REGISTRY:
            # Already registered (e.g., from previous call), skip
            continue
        try:
            adapter = TSBUADAdapter(config=config)
            REGISTRY[name] = adapter
            registered.append(name)
        except Exception:
            # If an individual algorithm fails to register (e.g., class
            # not found in TSB-UAD package), skip it silently but log
            # could be added in M2
            continue

    return registered


# Auto-register on import when TSB-UAD is available
register_tsbuad_algorithms()
