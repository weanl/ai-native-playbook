"""CLI commands for nextaiops_algo."""

import json
from pathlib import Path
from typing import Annotated

import typer

from nextaiops_algo.algorithms.registry import list_algorithms
from nextaiops_algo.pipeline import run_experiment
from nextaiops_algo.storage.sqlite_tracking import SqliteTrackingStore

app = typer.Typer(
    name="nextaiops_algo",
    help="NextAIOps Algorithm Platform - CLI interface",
)


@app.command()
def run(
    data: Annotated[Path, typer.Option("--data", help="Path to input CSV file")] = ...,  # type: ignore[assignment]
    algo: Annotated[str, typer.Option("--algo", help="Algorithm name to use")] = "three_sigma",
    params: Annotated[str, typer.Option("--params", help="Algorithm parameters as JSON string")] = "{}",
    output: Annotated[Path | None, typer.Option("--output", help="Output directory for artifacts")] = None,
) -> None:
    """Run an anomaly detection experiment.

    Example:
        python -m nextaiops_algo run --data metrics.csv --algo three_sigma
        python -m nextaiops_algo run --data metrics.csv --algo three_sigma --params '{"k": 2}'
    """
    # Parse params JSON
    try:
        params_dict = json.loads(params)
    except json.JSONDecodeError as e:
        typer.echo(f"Error: Invalid JSON params: {e}", err=True)
        raise typer.Exit(1) from None

    # Run experiment
    typer.echo(f"Running experiment: algo={algo}, data={data}")
    result = run_experiment(
        dataset_path=data,
        algorithm_name=algo,
        params=params_dict,
        output_dir=output,
    )

    # Output results
    typer.echo("\nExperiment completed:")
    typer.echo(f"  run_id: {result.run_id}")
    typer.echo(f"  metrics: {result.metrics}")
    typer.echo(f"  viz.html: {Path(result.artifacts_path) / 'viz.html'}")


@app.command()
def list_algos() -> None:
    """List all registered algorithms."""
    algos = list_algorithms()
    if not algos:
        typer.echo("No algorithms registered.")
        return
    typer.echo("Registered algorithms:")
    for name in algos:
        typer.echo(f"  - {name}")


@app.command()
def list_runs(
    limit: Annotated[int, typer.Option("--limit", help="Maximum number of runs to display")] = 10,
) -> None:
    """List recent experiment runs."""
    store = SqliteTrackingStore()
    runs = store.list_runs(limit=limit)

    if not runs:
        typer.echo("No runs found.")
        return

    typer.echo(f"Recent runs (limit={limit}):")
    for run in runs:
        typer.echo(f"\n  run_id: {run.run_id}")
        typer.echo(f"    algorithm: {run.algorithm_name}")
        typer.echo(f"    status: {run.status}")
        typer.echo(f"    created: {run.created_at}")
        if run.params:
            typer.echo(f"    params: {run.params}")
