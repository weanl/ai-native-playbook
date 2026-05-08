"""SQLite-based implementation of TrackingStore."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from nextaiops_algo.core.experiment import ExperimentRun, RunStatus
from nextaiops_algo.core.tracking import TrackingStore


class SqliteTrackingStore(TrackingStore):
    """SQLite implementation of TrackingStore.

    Stores experiment runs in a SQLite database with two tables:
    - runs: run metadata (run_id, algorithm, params, status, etc.)
    - metrics: evaluation metrics per run

    Attributes:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        """Initialize SqliteTrackingStore.

        Args:
            db_path: Path to SQLite database file. If None, uses default path
                     under NEXTAIOPS_ALGO_HOME or ./.nextaiops_algo/.
        """
        if db_path is None:
            default_home = Path.home() / ".nextaiops_algo"
            db_path = default_home / "tracking.db"

        self.db_path = Path(db_path)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create database tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                dataset_version TEXT NOT NULL,
                algorithm_name TEXT NOT NULL,
                params_json TEXT NOT NULL,
                status TEXT NOT NULL,
                artifacts_path TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                run_id TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                value REAL NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            )
        """)

        conn.commit()
        conn.close()

    def log_run(self, run: ExperimentRun) -> None:
        """Log a new experiment run to the database.

        Args:
            run: The ExperimentRun to log.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO runs (run_id, dataset_version, algorithm_name, params_json,
                              status, artifacts_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            run.run_id,
            run.dataset_version,
            run.algorithm_name,
            json.dumps(run.params),
            run.status.value,
            run.artifacts_path,
            run.created_at.isoformat(),
        ))

        conn.commit()
        conn.close()

    def get_run(self, run_id: str) -> ExperimentRun | None:
        """Retrieve an experiment run by its ID.

        Args:
            run_id: The unique identifier of the run.

        Returns:
            The ExperimentRun if found, else None.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT run_id, dataset_version, algorithm_name, params_json,
                   status, artifacts_path, created_at
            FROM runs
            WHERE run_id = ?
        """, (run_id,))

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return ExperimentRun(
            run_id=row[0],
            dataset_version=row[1],
            algorithm_name=row[2],
            params=json.loads(row[3]),
            status=RunStatus(row[4]),
            artifacts_path=row[5],
            created_at=datetime.fromisoformat(row[6]),
        )

    def list_runs(self, limit: int | None = None) -> list[ExperimentRun]:
        """List experiment runs, optionally limited.

        Args:
            limit: Maximum number of runs to return. None means all runs.

        Returns:
            List of ExperimentRun records, ordered by creation time (newest first).
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if limit is None:
            cursor.execute("""
                SELECT run_id, dataset_version, algorithm_name, params_json,
                       status, artifacts_path, created_at
                FROM runs
                ORDER BY created_at DESC
            """)
        else:
            cursor.execute("""
                SELECT run_id, dataset_version, algorithm_name, params_json,
                       status, artifacts_path, created_at
                FROM runs
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        runs = []
        for row in rows:
            runs.append(ExperimentRun(
                run_id=row[0],
                dataset_version=row[1],
                algorithm_name=row[2],
                params=json.loads(row[3]),
                status=RunStatus(row[4]),
                artifacts_path=row[5],
                created_at=datetime.fromisoformat(row[6]),
            ))

        return runs

    def log_metric(self, run_id: str, metric_name: str, value: float) -> None:
        """Log a metric for a run.

        Args:
            run_id: The run ID this metric belongs to.
            metric_name: Name of the metric (e.g., "f1", "precision").
            value: Metric value.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO metrics (run_id, metric_name, value)
            VALUES (?, ?, ?)
        """, (run_id, metric_name, value))

        conn.commit()
        conn.close()

    def get_metrics(self, run_id: str) -> dict[str, float]:
        """Get all metrics for a run.

        Args:
            run_id: The run ID to query.

        Returns:
            Dict mapping metric_name to value.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT metric_name, value
            FROM metrics
            WHERE run_id = ?
        """, (run_id,))

        rows = cursor.fetchall()
        conn.close()

        return {row[0]: row[1] for row in rows}
