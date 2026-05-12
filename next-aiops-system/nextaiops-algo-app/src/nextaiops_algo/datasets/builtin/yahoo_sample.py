"""yahoo_sample builtin dataset — derived from golden data."""

from pathlib import Path

import pandas as pd

from nextaiops_algo.core.table import FieldRole, Table, TableSchema
from nextaiops_algo.datasets.registry import BUILTIN_REGISTRY


class YahooSampleDataset:
    """Small Yahoo-like univariate time series for smoke and UI demo."""

    name = "yahoo_sample"
    description = "Small Yahoo-like univariate time series for smoke and UI demo."
    n_points = 1000
    source = "TSB-UAD Public / Yahoo (derived from golden data)"

    def load(self) -> Table:
        """Load yahoo_sample from packaged CSV."""
        data_dir = Path(__file__).parent / "data"
        df = pd.read_csv(data_dir / "yahoo_sample.csv")
        roles = {
            "timestamp": FieldRole.TIMESTAMP,
            "value": FieldRole.METRIC,
            "is_anomaly": FieldRole.LABEL,
        }
        schema = TableSchema(roles=roles)
        return Table(df=df, schema=schema)


BUILTIN_REGISTRY["yahoo_sample"] = YahooSampleDataset()
