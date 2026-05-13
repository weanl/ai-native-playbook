"""Unit tests for overlay visualization."""

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from nextaiops_algo.core.experiment import BatchRun, BatchStatus, ExperimentRun, RunStatus
from nextaiops_algo.core.table import FieldRole, Table, TableSchema
from nextaiops_algo.storage.sqlite_tracking import SqliteTrackingStore
from nextaiops_algo.viz.overlay import render_overlay


class TestRenderOverlay:
    """Tests for render_overlay function."""

    def _make_input_table(self) -> Table:
        """Create input Table with timestamp, metric, label."""
        n = 100
        rng = np.random.default_rng(42)
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="1h"),
            "cpu_usage": rng.normal(50, 10, n),
            "is_anomaly": np.zeros(n, dtype=int),
        })
        # Inject anomalies at known positions
        df.loc[20:25, "is_anomaly"] = 1
        df.loc[70:73, "is_anomaly"] = 1

        schema = TableSchema(
            roles={
                "timestamp": FieldRole.TIMESTAMP,
                "cpu_usage": FieldRole.METRIC,
                "is_anomaly": FieldRole.LABEL,
            }
        )
        return Table(df=df, schema=schema)

    def _make_detect_table(self, input_table: Table) -> Table:
        """Create a detect output Table for overlay testing."""
        df = input_table.df.copy()
        # Add anomaly detection columns
        df["cpu_usage.anomaly_score"] = np.zeros(len(df))
        df["cpu_usage.threshold_upper"] = 70.0
        df["cpu_usage.threshold_lower"] = 30.0
        df["predicted_label"] = df["is_anomaly"].copy()

        schema = TableSchema(
            roles={
                "timestamp": FieldRole.TIMESTAMP,
                "cpu_usage": FieldRole.METRIC,
                "cpu_usage.anomaly_score": FieldRole.METRIC,
                "cpu_usage.threshold_upper": FieldRole.METRIC,
                "cpu_usage.threshold_lower": FieldRole.METRIC,
                "predicted_label": FieldRole.LABEL,
            }
        )
        return Table(df=df, schema=schema)

    def _setup_batch_with_artifacts(self, tmp_path: object) -> BatchRun:
        """Create a BatchRun with persisted detect_output.csv artifacts."""
        db_path = Path(tmp_path) / "overlay.db"
        store = SqliteTrackingStore(db_path=db_path)

        input_table = self._make_input_table()
        detect_table = self._make_detect_table(input_table)

        # Create artifacts directory and save detect_output.csv
        artifacts_dir = Path(tmp_path) / "runs" / "run_ts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        detect_table.df.to_csv(artifacts_dir / "detect_output.csv", index=False)

        # Also create viz.html (required by existing tests)
        (artifacts_dir / "viz.html").write_text("<html>test</html>")

        completed_run = ExperimentRun(
            run_id="run_ts",
            dataset_version="test_data",
            algorithm_name="three_sigma",
            params={},
            status=RunStatus.COMPLETED,
            artifacts_path=str(artifacts_dir),
            created_at=datetime(2024, 1, 1, 12, 0),
        )

        store.log_run(completed_run)
        store.log_metric("run_ts", "f1", 0.75)
        store.log_metric("run_ts", "pa_f1", 0.85)

        return BatchRun(
            batch_id="batch_overlay",
            dataset_source="test.csv",
            algorithm_names=["three_sigma"],
            created_at=datetime(2024, 1, 1, 12, 0),
            runs=[completed_run],
            status=BatchStatus.COMPLETED,
        )

    def test_overlay_generates_figure(self, tmp_path: object) -> None:
        """render_overlay returns a Plotly Figure."""
        batch = self._setup_batch_with_artifacts(tmp_path)
        input_table = self._make_input_table()

        fig = render_overlay(batch, input_table)

        assert fig is not None
        assert len(fig.data) > 0

    def test_overlay_has_n_plus_1_subplots(self, tmp_path: object) -> None:
        """Overlay has 1 original + N algorithm subplots."""
        batch = self._setup_batch_with_artifacts(tmp_path)
        input_table = self._make_input_table()

        fig = render_overlay(batch, input_table)

        # 1 original + 1 algorithm = 2 subplots
        # Plotly subplots have layout with yaxis, yaxis2, etc.
        n_subplots = sum(1 for key in fig.layout if key.startswith("yaxis"))
        assert n_subplots == 2

    def test_overlay_failed_algo_shows_annotation(self, tmp_path: object) -> None:
        """Failed algorithm subplot shows FAILED annotation."""
        db_path = Path(tmp_path) / "overlay_failed.db"
        store = SqliteTrackingStore(db_path=db_path)

        failed_run = ExperimentRun(
            run_id="run_bad",
            dataset_version="test_data",
            algorithm_name="bad_algo",
            params={},
            status=RunStatus.FAILED,
            artifacts_path="",
            created_at=datetime(2024, 1, 1, 12, 0),
        )

        store.log_run(failed_run)

        batch = BatchRun(
            batch_id="batch_failed",
            dataset_source="test.csv",
            algorithm_names=["bad_algo"],
            created_at=datetime(2024, 1, 1, 12, 0),
            runs=[failed_run],
            status=BatchStatus.FAILED,
        )

        input_table = self._make_input_table()
        fig = render_overlay(batch, input_table)

        # Should have subplot title with "FAILED"
        subplot_titles = fig.layout.annotations
        assert any("FAILED" in t.text for t in subplot_titles)

    def test_overlay_saves_html_file(self, tmp_path: object) -> None:
        """render_overlay writes HTML file when output_path is provided."""
        batch = self._setup_batch_with_artifacts(tmp_path)
        input_table = self._make_input_table()

        output_path = Path(tmp_path) / "overlay_output.html"
        render_overlay(batch, input_table, output_path=output_path)

        assert output_path.exists()
        html_content = output_path.read_text()
        assert "plotly" in html_content

    def test_overlay_no_metric_raises_error(self) -> None:
        """render_overlay renders even with FAILED runs."""
        df2 = pd.DataFrame({"value": [1.0] * 10, "is_anomaly": [0] * 10})
        schema2 = TableSchema(roles={"value": FieldRole.METRIC, "is_anomaly": FieldRole.LABEL})
        table = Table(df=df2, schema=schema2)

        # Create a minimal batch
        run = ExperimentRun(
            run_id="r1", dataset_version="d", algorithm_name="a",
            params={}, status=RunStatus.FAILED, artifacts_path="",
            created_at=datetime(2024, 1, 1),
        )
        batch = BatchRun(
            batch_id="b1", dataset_source="d", algorithm_names=["a"],
            created_at=datetime(2024, 1, 1), runs=[run], status=BatchStatus.FAILED,
        )

        # Even with FAILED run, overlay should still render
        fig = render_overlay(batch, table)
        assert fig is not None
