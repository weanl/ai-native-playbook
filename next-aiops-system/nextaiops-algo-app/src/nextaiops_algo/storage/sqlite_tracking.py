"""SQLite-based implementation of TrackingStore."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from nextaiops_algo.core.experiment import BatchRun, BatchStatus, ExperimentRun, RunStatus
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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS batches (
                batch_id TEXT PRIMARY KEY,
                dataset_source TEXT NOT NULL,
                algorithm_names_json TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS batch_runs (
                batch_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                algorithm_name TEXT NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT,
                PRIMARY KEY (batch_id, run_id),
                FOREIGN KEY (batch_id) REFERENCES batches(batch_id),
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

    # --- Batch tracking methods --- #

    def log_batch(self, batch: BatchRun) -> None:
        """Log a new batch run to the database.

        Args:
            batch: The BatchRun to log.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO batches (batch_id, dataset_source, algorithm_names_json,
                                  status, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            batch.batch_id,
            batch.dataset_source,
            json.dumps(batch.algorithm_names),
            batch.status.value,
            batch.created_at.isoformat(),
        ))

        for run in batch.runs:
            cursor.execute("""
                INSERT INTO batch_runs (batch_id, run_id, algorithm_name,
                                        status, error_message)
                VALUES (?, ?, ?, ?, ?)
            """, (
                batch.batch_id,
                run.run_id,
                run.algorithm_name,
                run.status.value,
                None,
            ))

        conn.commit()
        conn.close()

    def get_batch(self, batch_id: str) -> BatchRun | None:
        """Retrieve a batch run by its ID.

        Args:
            batch_id: The unique identifier of the batch.

        Returns:
            The BatchRun if found, else None.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT batch_id, dataset_source, algorithm_names_json,
                   status, created_at
            FROM batches
            WHERE batch_id = ?
        """, (batch_id,))

        row = cursor.fetchone()

        if row is None:
            conn.close()
            return None

        # Fetch associated batch_runs
        cursor.execute("""
            SELECT run_id, algorithm_name, status, error_message
            FROM batch_runs
            WHERE batch_id = ?
        """, (batch_id,))

        batch_run_rows = cursor.fetchall()
        conn.close()

        # Reconstruct ExperimentRun objects from the runs table
        runs: list[ExperimentRun] = []
        for br_row in batch_run_rows:
            run_id = br_row[0]
            experiment_run = self.get_run(run_id)
            if experiment_run is not None:
                runs.append(experiment_run)

        return BatchRun(
            batch_id=row[0],
            dataset_source=row[1],
            algorithm_names=json.loads(row[2]),
            created_at=datetime.fromisoformat(row[4]),
            runs=runs,
            status=BatchStatus(row[3]),
        )

    def list_batches(self, limit: int | None = None) -> list[BatchRun]:
        """List batch runs, optionally limited.

        Args:
            limit: Maximum number of batches to return. None means all.

        Returns:
            List of BatchRun records, ordered by creation time (newest first).
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if limit is None:
            cursor.execute("""
                SELECT batch_id FROM batches ORDER BY created_at DESC
            """)
        else:
            cursor.execute("""
                SELECT batch_id FROM batches ORDER BY created_at DESC LIMIT ?
            """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        batches: list[BatchRun] = []
        for row in rows:
            batch = self.get_batch(row[0])
            if batch is not None:
                batches.append(batch)

        return batches
