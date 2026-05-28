import pandas as pd

from nextaiops_algo.core.table import FieldRole, Table, TableSchema
from nextaiops_algo.pipeline.rolling_data import (
    SyntheticTimeConfig,
    build_day_partitions,
    cumulative_training_window,
    partition_tables,
    split_train_validate,
)


def test_rolling_data_e2e_with_real_timestamp() -> None:
    df = pd.DataFrame(
        {
            "timestamp": [
                "2024-05-01T10:00:00+08:00",
                "2024-05-01T16:00:00Z",
                "2024-05-02T00:00:00Z",
            ],
            "value": [10.0, 11.0, 12.0],
            "label": [0, 1, 0],
        }
    )
    table = Table(
        df=df,
        schema=TableSchema(
            roles={"timestamp": FieldRole.TIMESTAMP, "value": FieldRole.METRIC, "label": FieldRole.LABEL}
        ),
    )

    partitions = build_day_partitions(table, threshold=0.5)
    by_day = partition_tables(table, partitions)
    window = cumulative_training_window(by_day, "2024-05-02")
    train, validate = split_train_validate(window, 0.6)

    assert len(partitions) == 2
    assert len(window.df) == 3
    assert len(train.df) + len(validate.df) == 3


def test_rolling_data_e2e_with_synthetic_timestamp() -> None:
    df = pd.DataFrame({"seq": [0, 1, 2, 3], "value": [1.0, 2.0, 3.0, 4.0], "label": [1, 1, 0, 0]})
    table = Table(df=df, schema=TableSchema(roles={"seq": FieldRole.METRIC, "value": FieldRole.METRIC, "label": FieldRole.LABEL}))
    cfg = SyntheticTimeConfig(
        time_index_column="seq",
        synthetic_start_time="2024-01-01T00:00:00Z",
        synthetic_interval="12h",
    )
    partitions = build_day_partitions(table, synthetic_time=cfg)
    assert [p.date.isoformat() for p in partitions] == ["2024-01-01", "2024-01-02"]
