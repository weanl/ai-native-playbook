"""Unit tests for FsArtifactStore."""

import tempfile
from pathlib import Path

from nextaiops_algo.storage.fs_artifact import FsArtifactStore


class TestFsArtifactStore:
    """Tests for FsArtifactStore."""

    def test_put_creates_file(self) -> None:
        """Test put creates file with correct content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FsArtifactStore(base_path=Path(tmpdir) / "artifacts")

            data = b"test artifact content"
            path = store.put("run-001", "test.txt", data)

            assert path.exists()
            assert path.read_bytes() == data

    def test_put_creates_run_directory(self) -> None:
        """Test put creates run subdirectory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FsArtifactStore(base_path=Path(tmpdir) / "artifacts")

            data = b"content"
            path = store.put("run-001", "file.txt", data)

            assert path.parent.name == "run-001"
            assert path.parent.parent == Path(tmpdir) / "artifacts"

    def test_get_retrieves_existing_file(self) -> None:
        """Test get retrieves existing artifact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FsArtifactStore(base_path=Path(tmpdir) / "artifacts")

            data = b"artifact data"
            store.put("run-001", "artifact.bin", data)

            retrieved = store.get("run-001", "artifact.bin")
            assert retrieved == data

    def test_get_returns_none_for_missing_file(self) -> None:
        """Test get returns None for non-existent artifact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FsArtifactStore(base_path=Path(tmpdir) / "artifacts")

            retrieved = store.get("run-001", "missing.txt")
            assert retrieved is None

    def test_path_for_returns_expected_path(self) -> None:
        """Test path_for returns correct path (even if not exist)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FsArtifactStore(base_path=Path(tmpdir) / "artifacts")

            path = store.path_for("run-001", "viz.html")
            assert path == Path(tmpdir) / "artifacts" / "run-001" / "viz.html"

            # Path may not exist yet
            assert not path.exists()

    def put_and_get_multiple_artifacts(self) -> None:
        """Test storing and retrieving multiple artifacts for same run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FsArtifactStore(base_path=Path(tmpdir) / "artifacts")

            viz_data = b"<html>viz</html>"
            model_data = b"model bytes"

            store.put("run-001", "viz.html", viz_data)
            store.put("run-001", "model.pkl", model_data)

            assert store.get("run-001", "viz.html") == viz_data
            assert store.get("run-001", "model.pkl") == model_data
