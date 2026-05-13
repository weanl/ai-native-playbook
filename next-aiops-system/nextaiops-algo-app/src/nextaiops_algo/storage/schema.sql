-- SQLite schema for experiment tracking
-- Tables: runs, metrics, batches, batch_runs

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    dataset_version TEXT NOT NULL,
    algorithm_name TEXT NOT NULL,
    params_json TEXT NOT NULL,
    status TEXT NOT NULL,
    artifacts_path TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metrics (
    run_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    value REAL NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS batches (
    batch_id TEXT PRIMARY KEY,
    dataset_source TEXT NOT NULL,
    algorithm_names_json TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS batch_runs (
    batch_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    algorithm_name TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    PRIMARY KEY (batch_id, run_id),
    FOREIGN KEY (batch_id) REFERENCES batches(batch_id),
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);