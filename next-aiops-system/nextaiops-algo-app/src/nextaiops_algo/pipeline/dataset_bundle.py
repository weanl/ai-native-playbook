"""DatasetBundle loading utilities for multi-file experiment inputs."""

import zipfile
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from nextaiops_algo.core.exceptions import SchemaValidationError
from nextaiops_algo.core.table import Table
from nextaiops_algo.datasets.loaders import read_to_table

SUPPORTED_BUNDLE_SUFFIXES = {".csv", ".out", ".npy", ".npz"}


class DatasetFile(BaseModel):
    """A single supported file loaded as part of a dataset bundle."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    path: Path
    table: Table


class DatasetBundle(BaseModel):
    """A group of files treated as one dataset with a consistent schema."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    dataset_id: str
    files: list[DatasetFile] = Field(min_length=1)

    @property
    def file_count(self) -> int:
        """Return the number of files in the bundle."""
        return len(self.files)


def load_dataset_bundle(
    paths: Sequence[str | Path],
    dataset_id: str | None = None,
) -> DatasetBundle:
    """Load multiple supported files as a schema-consistent dataset bundle.

    Args:
        paths: Input file paths. Hidden files and unsupported suffixes are ignored.
        dataset_id: Optional stable label for the dataset bundle.

    Returns:
        DatasetBundle containing one loaded Table per file.

    Raises:
        SchemaValidationError: If no supported files are found, or schemas differ.
    """
    files: list[DatasetFile] = []
    for raw_path in sorted((Path(path) for path in paths), key=lambda p: p.name):
        if _should_ignore(raw_path):
            continue
        table = read_to_table(raw_path)
        files.append(DatasetFile(name=raw_path.name, path=raw_path, table=table))

    if not files:
        raise SchemaValidationError(
            "Dataset bundle contains no supported data files",
            context={"supported_suffixes": sorted(SUPPORTED_BUNDLE_SUFFIXES)},
        )

    _validate_consistent_schema(files)
    return DatasetBundle(dataset_id=dataset_id or _default_dataset_id(files), files=files)


def load_dataset_bundle_from_zip(
    zip_path: Path,
    extract_dir: Path,
    dataset_id: str | None = None,
) -> DatasetBundle:
    """Extract a zip file and load supported members as a dataset bundle.

    Args:
        zip_path: Path to a zip archive.
        extract_dir: Destination directory for extracted supported members.
        dataset_id: Optional stable label for the dataset bundle.

    Returns:
        DatasetBundle loaded from extracted supported files.

    Raises:
        SchemaValidationError: If the archive is invalid, unsafe, or has no data files.
    """
    if not zip_path.exists():
        raise FileNotFoundError(f"Zip file not found: {zip_path}")

    extracted_paths: list[Path] = []
    extract_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path) as archive:
            for info in sorted(archive.infolist(), key=lambda item: item.filename):
                member_path = Path(info.filename)
                if info.is_dir() or _should_ignore(member_path):
                    continue
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise SchemaValidationError(
                        "Zip archive contains unsafe member path",
                        context={"member": info.filename},
                    )
                output_path = extract_dir / member_path
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(archive.read(info))
                extracted_paths.append(output_path)
    except zipfile.BadZipFile:
        raise SchemaValidationError(
            "Uploaded file is not a valid zip archive",
            context={"file": str(zip_path)},
        ) from None

    return load_dataset_bundle(
        extracted_paths,
        dataset_id=dataset_id or zip_path.stem,
    )


def schema_signature(table: Table) -> tuple[tuple[str, str], ...]:
    """Return a comparable schema signature for bundle consistency checks."""
    return tuple((column, role.value) for column, role in table.schema.roles.items())


def _validate_consistent_schema(files: Sequence[DatasetFile]) -> None:
    expected = schema_signature(files[0].table)
    expected_file = files[0].name

    for file in files[1:]:
        actual = schema_signature(file.table)
        if actual != expected:
            raise SchemaValidationError(
                "Dataset bundle schema mismatch",
                context={
                    "expected_file": expected_file,
                    "expected_schema": list(expected),
                    "actual_file": file.name,
                    "actual_schema": list(actual),
                },
            )


def _should_ignore(path: Path) -> bool:
    return path.name.startswith(".") or path.suffix.lower() not in SUPPORTED_BUNDLE_SUFFIXES


def _default_dataset_id(files: Sequence[DatasetFile]) -> str:
    if len(files) == 1:
        return files[0].name
    return f"{files[0].name}+{len(files) - 1}"
