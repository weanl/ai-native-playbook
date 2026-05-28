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

CREATE TABLE IF NOT EXISTS rolling_experiments (
    experiment_id TEXT PRIMARY KEY,
    dataset_path TEXT NOT NULL,
    date_column TEXT,
    policy_json TEXT NOT NULL,
    algorithms_json TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rolling_day_cycles (
    experiment_id TEXT NOT NULL,
    cutoff_day TEXT NOT NULL,
    algorithm_name TEXT NOT NULL,
    params_json TEXT NOT NULL,
    train_rows INTEGER NOT NULL,
    validate_rows INTEGER NOT NULL,
    active_interval_start TEXT,
    active_interval_end TEXT,
    status TEXT NOT NULL,
    exclusion_reason TEXT,
    error_message TEXT,
    active_model_id TEXT,
    metrics_json TEXT NOT NULL,
    FOREIGN KEY (experiment_id) REFERENCES rolling_experiments(experiment_id)
);

CREATE TABLE IF NOT EXISTS rolling_predictions (
    experiment_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    algorithm_name TEXT NOT NULL,
    params_json TEXT NOT NULL,
    cutoff_day TEXT NOT NULL,
    active_model_id TEXT NOT NULL,
    predicted_label INTEGER NOT NULL,
    score REAL,
    label INTEGER,
    FOREIGN KEY (experiment_id) REFERENCES rolling_experiments(experiment_id)
);
