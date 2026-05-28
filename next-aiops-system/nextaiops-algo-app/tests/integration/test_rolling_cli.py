from pathlib import Path

import pandas as pd
from typer.testing import CliRunner

from nextaiops_algo.cli.commands import app


def test_rolling_cli_run_and_list(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("HOME", str(tmp_path))
    data_path = tmp_path / "multi_day.csv"
    rows = []
    for day in range(1, 4):
        for hour in range(10):
            is_anomaly = hour >= 8
            rows.append({
                "timestamp": f"2024-03-0{day}T{hour:02d}:00:00Z",
                "value": 90.0 if is_anomaly else float(8 + hour % 2),
                "is_anomaly": 1 if is_anomaly else 0,
            })
    pd.DataFrame(rows).to_csv(data_path, index=False)

    runner = CliRunner()
    result = runner.invoke(app, [
        "rolling",
        "--data",
        str(data_path),
        "--algos",
        "three_sigma,iqr",
    ])

    assert result.exit_code == 0
    assert "Rolling experiment completed" in result.stdout
    assert "experiment_id:" in result.stdout

    list_result = runner.invoke(app, ["list-rolling", "--limit", "5"])
    assert list_result.exit_code == 0
    assert "Recent rolling experiments" in list_result.stdout
