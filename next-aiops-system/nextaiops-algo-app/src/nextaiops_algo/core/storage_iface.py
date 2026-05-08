"""Artifact store protocol - interface for artifact storage."""

from pathlib import Path
from typing import Protocol


class ArtifactStore(Protocol):
    """Protocol for storing and retrieving artifacts.

    Artifacts include model files, visualization HTML, logs, etc.
    """

    def put(self, run_id: str, name: str, data: bytes) -> Path:
        """Store an artifact for a run.

        Args:
            run_id: The run ID this artifact belongs to.
            name: Artifact name (e.g., "viz.html", "model.pkl").
            data: Artifact content as bytes.

        Returns:
            Path to the stored artifact.
        """
        ...

    def get(self, run_id: str, name: str) -> bytes | None:
        """Retrieve an artifact for a run.

        Args:
            run_id: The run ID to query.
            name: Artifact name to retrieve.

        Returns:
            Artifact content as bytes if found, else None.
        """
        ...

    def path_for(self, run_id: str, name: str) -> Path:
        """Get the path where an artifact would be stored.

        Args:
            run_id: The run ID.
            name: Artifact name.

        Returns:
            Path to the artifact location (may not exist yet).
        """
        ...
