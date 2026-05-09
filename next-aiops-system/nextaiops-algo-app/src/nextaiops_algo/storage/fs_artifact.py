"""File system-based implementation of ArtifactStore."""

from pathlib import Path

from nextaiops_algo.core.storage_iface import ArtifactStore


class FsArtifactStore(ArtifactStore):
    """File system implementation of ArtifactStore.

    Stores artifacts (model files, visualizations, logs) in a directory structure
    under a base path. Each run has its own subdirectory.

    Attributes:
        base_path: Root directory for artifact storage.
    """

    def __init__(self, base_path: Path | str | None = None) -> None:
        """Initialize FsArtifactStore.

        Args:
            base_path: Root directory for artifacts. If None, uses default path
                       under NEXTAIOPS_ALGO_HOME or ./.nextaiops_algo/.
        """
        if base_path is None:
            base_path = Path.home() / ".nextaiops_algo" / "runs"

        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def put(self, run_id: str, name: str, data: bytes) -> Path:
        """Store an artifact for a run.

        Args:
            run_id: The run ID this artifact belongs to.
            name: Artifact name (e.g., "viz.html", "model.pkl").
            data: Artifact content as bytes.

        Returns:
            Path to the stored artifact.
        """
        run_dir = self.base_path / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        artifact_path = run_dir / name
        artifact_path.write_bytes(data)

        return artifact_path

    def get(self, run_id: str, name: str) -> bytes | None:
        """Retrieve an artifact for a run.

        Args:
            run_id: The run ID to query.
            name: Artifact name to retrieve.

        Returns:
            Artifact content as bytes if found, else None.
        """
        artifact_path = self.base_path / run_id / name

        if not artifact_path.exists():
            return None

        return artifact_path.read_bytes()

    def path_for(self, run_id: str, name: str) -> Path:
        """Get the path where an artifact would be stored.

        Args:
            run_id: The run ID.
            name: Artifact name.

        Returns:
            Path to the artifact location (may not exist yet).
        """
        return self.base_path / run_id / name
