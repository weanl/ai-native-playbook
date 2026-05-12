"""nab_sample builtin dataset — NAB-style anomaly segments."""

from pathlib import Path

import pandas as pd

from nextaiops_algo.core.table import FieldRole, Table, TableSchema
from nextaiops_algo.datasets.registry import BUILTIN_REGISTRY


class NabSampleDataset:
    """Small NAB-style univariate time series with 3 anomaly segments."""

    name = "nab_sample"
    description = "Small NAB-style univariate time series with 3 anomaly segments."
    n_points = 500
    source = "NAB-style synthetic (generated)"

    def load(self) -> Table:
        """Load nab_sample from packaged .out file."""
        data_dir = Path(__file__).parent / "data"
        df = pd.read_csv(data_dir / "nab_sample.out", sep=r"\s+", header=None)
        df.columns = ["value", "is_anomaly"]
        roles = {"value": FieldRole.METRIC, "is_anomaly": FieldRole.LABEL}
        schema = TableSchema(roles=roles)
        return Table(df=df, schema=schema)


BUILTIN_REGISTRY["nab_sample"] = NabSampleDataset()
