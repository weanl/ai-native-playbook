"""nasa_msl_sample builtin dataset — NASA MSL-style scattered anomalies."""

from pathlib import Path

import numpy as np
import pandas as pd

from nextaiops_algo.core.table import FieldRole, Table, TableSchema
from nextaiops_algo.datasets.registry import BUILTIN_REGISTRY


class NasMslSampleDataset:
    """Small NASA MSL-style univariate time series with scattered anomalies."""

    name = "nasa_msl_sample"
    description = "Small NASA MSL-style univariate time series with 4 scattered anomalies."
    n_points = 800
    source = "NASA MSL-style synthetic (generated)"

    def load(self) -> Table:
        """Load nasa_msl_sample from packaged .npz file."""
        data_dir = Path(__file__).parent / "data"
        npz = np.load(data_dir / "nasa_msl_sample.npz")
        data = npz["data"]
        labels = npz["label"]

        df = pd.DataFrame({"value": data, "is_anomaly": labels})
        roles = {"value": FieldRole.METRIC, "is_anomaly": FieldRole.LABEL}
        schema = TableSchema(roles=roles)
        return Table(df=df, schema=schema)


BUILTIN_REGISTRY["nasa_msl_sample"] = NasMslSampleDataset()
