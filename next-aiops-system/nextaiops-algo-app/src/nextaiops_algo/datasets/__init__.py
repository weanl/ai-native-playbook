"""Datasets module — data input diversification for M1 batch experiments.

Provides:
- Loaders: CSV, TSB-UAD .out, npy, npz format → Table conversion
- Registry: Builtin dataset discovery
- Unified entry: read_to_table(path_or_name) for auto-dispatch
"""

from nextaiops_algo.datasets.builtin import (
    NabSampleDataset,
    NasMslSampleDataset,
    YahooSampleDataset,
)
from nextaiops_algo.datasets.loaders import (
    read_csv_to_table,
    read_npy_to_table,
    read_npz_to_table,
    read_to_table,
    read_tsbuad_out_to_table,
)
from nextaiops_algo.datasets.registry import BUILTIN_REGISTRY, list_builtin

__all__ = [
    "BUILTIN_REGISTRY",
    "NabSampleDataset",
    "NasMslSampleDataset",
    "YahooSampleDataset",
    "list_builtin",
    "read_csv_to_table",
    "read_npy_to_table",
    "read_npz_to_table",
    "read_to_table",
    "read_tsbuad_out_to_table",
]
