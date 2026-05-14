"""Unit tests for DatasetBundle loading."""

import zipfile
from pathlib import Path

import pandas as pd
import pytest

from nextaiops_algo.core.exceptions import SchemaValidationError
from nextaiops_algo.pipeline.dataset_bundle import (
    load_dataset_bundle,
    load_dataset_bundle_from_zip,
    schema_signature,
)


def _write_csv(path: Path, metric_name: str = "value") -> Path:
    df = pd.DataFrame(
        {
            "timestamp": [1, 2, 3, 4],
            metric_name: [1.0, 2.0, 10.0, 3.0],
            "is_anomaly": [0, 0, 1, 0],
        }
    )
    df.to_csv(path, index=False)
    return path


def test_load_dataset_bundle_accepts_multiple_consistent_csv_files(tmp_path: Path) -> None:
    """Multiple CSV files with identical roles load as one bundle."""
    first = _write_csv(tmp_path / "a.csv")
    second = _write_csv(tmp_path / "b.csv")

    bundle = load_dataset_bundle([second, first], dataset_id="upload")

    assert bundle.dataset_id == "upload"
    assert bundle.file_count == 2
    assert [file.name for file in bundle.files] == ["a.csv", "b.csv"]
    assert schema_signature(bundle.files[0].table) == (
        ("timestamp", "timestamp"),
        ("value", "metric"),
        ("is_anomaly", "label"),
    )


def test_load_dataset_bundle_rejects_schema_mismatch_with_file_context(tmp_path: Path) -> None:
    """Bundle schema mismatches fail fast and include conflicting file names."""
    first = _write_csv(tmp_path / "a.csv")
    second = _write_csv(tmp_path / "b.csv", metric_name="other_value")

    with pytest.raises(SchemaValidationError) as exc_info:
        load_dataset_bundle([first, second])

    assert "Dataset bundle schema mismatch" in str(exc_info.value)
    assert exc_info.value.context["expected_file"] == "a.csv"
    assert exc_info.value.context["actual_file"] == "b.csv"


def test_load_dataset_bundle_ignores_hidden_and_unsupported_files(tmp_path: Path) -> None:
    """Hidden files and unsupported suffixes do not enter bundle loading."""
    csv_path = _write_csv(tmp_path / "a.csv")
    _write_csv(tmp_path / ".hidden.csv")
    (tmp_path / "notes.txt").write_text("ignore me")

    bundle = load_dataset_bundle([csv_path, tmp_path / ".hidden.csv", tmp_path / "notes.txt"])

    assert bundle.file_count == 1
    assert bundle.files[0].name == "a.csv"


def test_load_dataset_bundle_from_zip_supports_nested_tsbuad_like_layout(tmp_path: Path) -> None:
    """Zip loading preserves nested supported files like a TSB-AD-U directory dump."""
    zip_path = tmp_path / "dataset.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        first = tmp_path / "001_NAB_id_1_Facility_tr_1007_1st_2014.csv"
        second = tmp_path / "002_NAB_id_2_WebService_tr_1500_1st_4106.csv"
        _write_csv(first)
        _write_csv(second)
        archive.write(first, "TSB-AD-U/001_NAB_id_1_Facility_tr_1007_1st_2014.csv")
        archive.write(second, "TSB-AD-U/002_NAB_id_2_WebService_tr_1500_1st_4106.csv")
        archive.writestr("TSB-AD-U/.DS_Store", "ignore")
        archive.writestr("TSB-AD-U/readme.txt", "ignore")

    bundle = load_dataset_bundle_from_zip(zip_path, extract_dir=tmp_path / "extract")

    assert bundle.file_count == 2
    assert bundle.files[0].name == "001_NAB_id_1_Facility_tr_1007_1st_2014.csv"
    assert bundle.files[1].path.exists()


def test_load_dataset_bundle_from_zip_rejects_unsafe_member(tmp_path: Path) -> None:
    """Zip path traversal is rejected before extraction."""
    zip_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("../bad.csv", "value,is_anomaly\n1,0\n")

    with pytest.raises(SchemaValidationError) as exc_info:
        load_dataset_bundle_from_zip(zip_path, extract_dir=tmp_path / "extract")

    assert "unsafe member path" in str(exc_info.value)
