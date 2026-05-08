"""Unit tests for TableSchema."""


from nextaiops_algo.core import FieldRole, TableSchema


class TestTableSchemaColumnsOf:
    """Tests for TableSchema.columns_of() method."""

    def test_columns_of_returns_correct_columns(self) -> None:
        """columns_of() returns only columns with the specified role."""
        schema = TableSchema(
            roles={
                "ts": FieldRole.TIMESTAMP,
                "value1": FieldRole.METRIC,
                "value2": FieldRole.METRIC,
                "label": FieldRole.LABEL,
            }
        )
        assert schema.columns_of(FieldRole.TIMESTAMP) == ["ts"]
        assert schema.columns_of(FieldRole.METRIC) == ["value1", "value2"]
        assert schema.columns_of(FieldRole.LABEL) == ["label"]

    def test_columns_of_returns_empty_list_for_missing_role(self) -> None:
        """columns_of() returns empty list when no columns have the role."""
        schema = TableSchema(roles={"value": FieldRole.METRIC})
        assert schema.columns_of(FieldRole.TIMESTAMP) == []
        assert schema.columns_of(FieldRole.LABEL) == []

    def test_columns_of_order_is_stable(self) -> None:
        """columns_of() returns columns in declaration order."""
        # Declaration order: value3, value1, value2
        schema = TableSchema(
            roles={
                "value3": FieldRole.METRIC,
                "value1": FieldRole.METRIC,
                "value2": FieldRole.METRIC,
            }
        )
        metric_cols = schema.columns_of(FieldRole.METRIC)
        assert metric_cols == ["value3", "value1", "value2"]

    def test_columns_of_order_preserves_dict_insertion_order(self) -> None:
        """columns_of() preserves dict insertion order (Python 3.7+ guarantee)."""
        schema = TableSchema(
            roles={
                "a": FieldRole.METRIC,
                "b": FieldRole.METRIC,
                "c": FieldRole.METRIC,
                "d": FieldRole.TIMESTAMP,
                "e": FieldRole.LABEL,
            }
        )
        assert schema.columns_of(FieldRole.METRIC) == ["a", "b", "c"]
        assert schema.columns_of(FieldRole.TIMESTAMP) == ["d"]
        assert schema.columns_of(FieldRole.LABEL) == ["e"]


class TestTableSchemaRoles:
    """Tests for TableSchema.roles field."""

    def test_roles_mapping_preserves_all_entries(self) -> None:
        """All role entries are preserved in the schema."""
        schema = TableSchema(
            roles={
                "ts": FieldRole.TIMESTAMP,
                "value": FieldRole.METRIC,
                "label": FieldRole.LABEL,
            }
        )
        assert len(schema.roles) == 3
        assert schema.roles["ts"] == FieldRole.TIMESTAMP
        assert schema.roles["value"] == FieldRole.METRIC
        assert schema.roles["label"] == FieldRole.LABEL

    def test_roles_with_duplicate_column_names(self) -> None:
        """Schema accepts different roles for same column name would be invalid at Table level."""
        # This schema alone is valid; Table validation will catch missing columns
        schema = TableSchema(
            roles={
                "col1": FieldRole.METRIC,
                "col2": FieldRole.METRIC,
            }
        )
        assert len(schema.roles) == 2
