"""Unit tests for heatmap visualization."""

from datetime import datetime

from nextaiops_algo.core.experiment import BatchRun, BatchStatus, ExperimentRun, RunStatus
from nextaiops_algo.storage.sqlite_tracking import SqliteTrackingStore
from nextaiops_algo.viz.heatmap import render_heatmap


class TestRenderHeatmap:
    """Tests for render_heatmap function."""

    def _make_run(self, algo_name: str, status: RunStatus = RunStatus.COMPLETED) -> ExperimentRun:
        return ExperimentRun(
            run_id=f"run_{algo_name}",
            dataset_version="test_data",
            algorithm_name=algo_name,
            params={},
            status=status,
            artifacts_path="/tmp/test",
            created_at=datetime(2024, 1, 1, 12, 0),
        )

    def _make_batch_with_metrics(self, tmp_path: object) -> tuple[BatchRun, SqliteTrackingStore]:
        """Create a BatchRun with logged runs and varying metrics."""
        store = SqliteTrackingStore(db_path=tmp_path / "heatmap.db")

        runs = [
            self._make_run("three_sigma"),
            self._make_run("iqr"),
        ]

        for run in runs:
            store.log_run(run)

        # iqr has higher metrics
        store.log_metric("run_three_sigma", "precision", 0.6)
        store.log_metric("run_three_sigma", "recall", 0.5)
        store.log_metric("run_three_sigma", "f1", 0.545)
        store.log_metric("run_three_sigma", "pa_precision", 0.7)
        store.log_metric("run_three_sigma", "pa_recall", 0.6)
        store.log_metric("run_three_sigma", "pa_f1", 0.646)

        store.log_metric("run_iqr", "precision", 0.8)
        store.log_metric("run_iqr", "recall", 0.7)
        store.log_metric("run_iqr", "f1", 0.747)
        store.log_metric("run_iqr", "pa_precision", 0.9)
        store.log_metric("run_iqr", "pa_recall", 0.8)
        store.log_metric("run_iqr", "pa_f1", 0.847)

        return BatchRun(
            batch_id="batch_heatmap",
            dataset_source="test.csv",
            algorithm_names=["three_sigma", "iqr"],
            created_at=datetime(2024, 1, 1, 12, 0),
            runs=runs,
            status=BatchStatus.COMPLETED,
        ), store

    def test_heatmap_generates_figure(self, tmp_path: object) -> None:
        """render_heatmap returns a Plotly Figure."""
        batch, store = self._make_batch_with_metrics(tmp_path)
        fig = render_heatmap(batch, store=store)

        assert fig is not None
        assert len(fig.data) == 1  # One Heatmap trace

    def test_heatmap_y_axis_has_algorithm_names(self, tmp_path: object) -> None:
        """Heatmap Y-axis shows algorithm names."""
        batch, store = self._make_batch_with_metrics(tmp_path)
        fig = render_heatmap(batch, store=store)

        heatmap = fig.data[0]
        assert set(heatmap.y) == {"three_sigma", "iqr"}

    def test_heatmap_x_axis_has_metric_names(self, tmp_path: object) -> None:
        """Heatmap X-axis shows display metric names."""
        batch, store = self._make_batch_with_metrics(tmp_path)
        fig = render_heatmap(batch, store=store)

        heatmap = fig.data[0]
        expected = ["Precision", "Recall", "F1", "PA-Precision", "PA-Recall", "PA-F1"]
        assert list(heatmap.x) == expected

    def test_heatmap_color_mapping_correct(self, tmp_path: object) -> None:
        """Heatmap z-values reflect actual metric values (higher = better)."""
        batch, store = self._make_batch_with_metrics(tmp_path)
        fig = render_heatmap(batch, store=store)

        heatmap = fig.data[0]
        z = heatmap.z

        # iqr row should have higher values than three_sigma
        iqr_row = z[1]
        ts_row = z[0]

        # PA-F1 is the last column (index 5)
        assert iqr_row[5] > ts_row[5]

    def test_heatmap_failed_algo_shows_nan(self, tmp_path: object) -> None:
        """Failed algorithm shows NaN in heatmap cells."""
        store = SqliteTrackingStore(db_path=tmp_path / "heatmap_failed.db")

        completed_run = self._make_run("three_sigma")
        failed_run = ExperimentRun(
            run_id="run_bad",
            dataset_version="test_data",
            algorithm_name="bad_algo",
            params={},
            status=RunStatus.FAILED,
            artifacts_path="",
            created_at=datetime(2024, 1, 1, 12, 0),
        )

        store.log_run(completed_run)
        store.log_run(failed_run)
        store.log_metric("run_three_sigma", "pa_f1", 0.5)

        batch = BatchRun(
            batch_id="batch_failed",
            dataset_source="test.csv",
            algorithm_names=["three_sigma", "bad_algo"],
            created_at=datetime(2024, 1, 1, 12, 0),
            runs=[completed_run, failed_run],
            status=BatchStatus.PARTIAL_FAILED,
        )

        fig = render_heatmap(batch, store=store)

        heatmap = fig.data[0]
        # bad_algo row (index 1) should have all NaN
        for val in heatmap.z[1]:
            assert val != val  # NaN is not equal to itself

    def test_heatmap_saves_html_file(self, tmp_path: object) -> None:
        """render_heatmap writes HTML file when output_path is provided."""
        from pathlib import Path

        batch, store = self._make_batch_with_metrics(tmp_path)
        output_path = Path(tmp_path) / "heatmap_output.html"
        render_heatmap(batch, output_path=output_path, store=store)

        assert output_path.exists()
        html_content = output_path.read_text()
        assert "plotly" in html_content

    def test_heatmap_custom_metrics_list(self, tmp_path: object) -> None:
        """Heatmap can show a subset of metrics."""
        batch, store = self._make_batch_with_metrics(tmp_path)
        fig = render_heatmap(batch, metrics=["f1", "pa_f1"], store=store)

        heatmap = fig.data[0]
        assert list(heatmap.x) == ["F1", "PA-F1"]

    def test_heatmap_text_template_shows_values(self, tmp_path: object) -> None:
        """Heatmap cells display formatted values."""
        batch, store = self._make_batch_with_metrics(tmp_path)
        fig = render_heatmap(batch, store=store)

        heatmap = fig.data[0]
        # text should have formatted values like "0.65"
        assert heatmap.text is not None
        assert len(heatmap.text) == 2  # 2 algorithms
