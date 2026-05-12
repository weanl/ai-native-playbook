"""Unit tests for datasets/registry.py and builtin datasets."""

import pytest

from nextaiops_algo.core.table import FieldRole
from nextaiops_algo.datasets.registry import BUILTIN_REGISTRY, get_builtin, list_builtin


class TestDatasetRegistry:
    """Tests for dataset registry."""

    def test_list_builtin_returns_at_least_three(self) -> None:
        """list_builtin() returns >= 3 dataset names."""
        names = list_builtin()
        assert len(names) >= 3
        assert "yahoo_sample" in names
        assert "nab_sample" in names
        assert "nasa_msl_sample" in names

    def test_get_builtin_yahoo_sample(self) -> None:
        """get_builtin('yahoo_sample') returns valid dataset."""
        ds = get_builtin("yahoo_sample")
        assert ds.name == "yahoo_sample"
        assert ds.n_points > 0

    def test_get_builtin_unknown_raises(self) -> None:
        """get_builtin with unknown name raises KeyError."""
        with pytest.raises(KeyError, match="Unknown builtin"):
            get_builtin("nonexistent_dataset")

    def test_builtin_registry_contains_all(self) -> None:
        """BUILTIN_REGISTRY contains all registered datasets."""
        assert set(BUILTIN_REGISTRY.keys()) == set(list_builtin())


class TestBuiltinYahooSample:
    """Tests for yahoo_sample builtin dataset."""

    def test_load_returns_table(self) -> None:
        """yahoo_sample.load() returns a valid Table."""
        ds = get_builtin("yahoo_sample")
        table = ds.load()
        assert table is not None
        assert len(table.df) == 1000

    def test_has_timestamp_metric_label(self) -> None:
        """yahoo_sample has TIMESTAMP, METRIC, and LABEL roles."""
        table = get_builtin("yahoo_sample").load()
        roles_set = set(table.schema.roles.values())
        assert FieldRole.TIMESTAMP in roles_set
        assert FieldRole.METRIC in roles_set
        assert FieldRole.LABEL in roles_set

    def test_anomalies_present(self) -> None:
        """yahoo_sample has some anomaly points."""
        table = get_builtin("yahoo_sample").load()
        labels = table.labels()
        assert labels is not None
        assert labels.sum() > 0


class TestBuiltinNabSample:
    """Tests for nab_sample builtin dataset."""

    def test_load_returns_table(self) -> None:
        """nab_sample.load() returns a valid Table."""
        ds = get_builtin("nab_sample")
        table = ds.load()
        assert table is not None
        assert len(table.df) == 500

    def test_has_metric_and_label(self) -> None:
        """nab_sample has METRIC and LABEL roles (no TIMESTAMP)."""
        table = get_builtin("nab_sample").load()
        roles_set = set(table.schema.roles.values())
        assert FieldRole.METRIC in roles_set
        assert FieldRole.LABEL in roles_set
        assert FieldRole.TIMESTAMP not in roles_set

    def test_anomalies_present(self) -> None:
        """nab_sample has anomaly segments."""
        table = get_builtin("nab_sample").load()
        labels = table.labels()
        assert labels is not None
        assert labels.sum() > 0


class TestBuiltinNasaMslSample:
    """Tests for nasa_msl_sample builtin dataset."""

    def test_load_returns_table(self) -> None:
        """nasa_msl_sample.load() returns a valid Table."""
        ds = get_builtin("nasa_msl_sample")
        table = ds.load()
        assert table is not None
        assert len(table.df) == 800

    def test_has_metric_and_label(self) -> None:
        """nasa_msl_sample has METRIC and LABEL roles."""
        table = get_builtin("nasa_msl_sample").load()
        roles_set = set(table.schema.roles.values())
        assert FieldRole.METRIC in roles_set
        assert FieldRole.LABEL in roles_set

    def test_scattered_anomalies(self) -> None:
        """nasa_msl_sample has scattered anomaly points."""
        table = get_builtin("nasa_msl_sample").load()
        labels = table.labels()
        assert labels is not None
        assert labels.sum() > 0
