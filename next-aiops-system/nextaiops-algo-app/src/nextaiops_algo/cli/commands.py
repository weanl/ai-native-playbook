"""CLI commands for nextaiops_algo."""

import json
from pathlib import Path
from typing import Annotated, Literal

import typer

from nextaiops_algo.algorithms.registry import list_algorithms
from nextaiops_algo.pipeline import run_batch, run_experiment
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


@app.command()
def batch(
    data: Annotated[Path, typer.Option("--data", help="Path to input data or builtin dataset name")] = ...,  # type: ignore[assignment]
    algos: Annotated[str, typer.Option("--algos", help="Comma-separated algorithm names, or 'all'")] = "all",
    output: Annotated[Path | None, typer.Option("--output", help="Output directory for artifacts")] = None,
) -> None:
    """Run a batch experiment with multiple algorithms on one dataset.

    Example:
        python -m nextaiops_algo batch --data metrics.csv --algos three_sigma,iqr
        python -m nextaiops_algo batch --data metrics.csv --algos all
    """
    algo_list: list[str] | Literal["__all__"] = "__all__" if algos.lower() == "all" else [a.strip() for a in algos.split(",")]

    typer.echo(f"Running batch: algos={algo_list}, data={data}")

    result = run_batch(
        dataset=data,
        algorithms=algo_list,
        output_dir=output,
    )

    typer.echo("\nBatch completed:")
    typer.echo(f"  batch_id: {result.batch_id}")
    typer.echo(f"  status: {result.status}")

    for run in result.runs:
        status_icon = "✓" if run.status.value == "completed" else "✗"
        typer.echo(f"  [{status_icon}] {run.algorithm_name}: {run.status}")

    typer.echo("\nUse 'list-batches' to query batch history.")


@app.command()
def list_batches(
    limit: Annotated[int, typer.Option("--limit", help="Maximum number of batches to display")] = 20,
) -> None:
    """List recent batch experiment runs."""
    store = SqliteTrackingStore()
    batches = store.list_batches(limit=limit)

    if not batches:
        typer.echo("No batches found.")
        return

    typer.echo(f"Recent batches (limit={limit}):")
    for b in batches:
        typer.echo(f"\n  batch_id: {b.batch_id}")
        typer.echo(f"    dataset: {b.dataset_source}")
        typer.echo(f"    algorithms: {b.algorithm_names}")
        typer.echo(f"    status: {b.status}")
        typer.echo(f"    created: {b.created_at}")
