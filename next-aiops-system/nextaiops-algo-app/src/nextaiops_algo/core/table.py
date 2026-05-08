"""Table - unified data carrier for algorithm I/O."""

from enum import StrEnum

import pandas as pd
from pydantic import BaseModel, ConfigDict, PrivateAttr

from .exceptions import SchemaValidationError


class FieldRole(StrEnum):
    """Role of a column in Table.

    M0 supports only these 3 roles. New roles require ADR.
    """

    TIMESTAMP = "timestamp"
    METRIC = "metric"
    LABEL = "label"


class TableSchema(BaseModel):
    """Schema defining column roles for a Table.

    Attributes:
        roles: Mapping from column name to FieldRole.
    """

    roles: dict[str, FieldRole]

    def columns_of(self, role: FieldRole) -> list[str]:
        """Get column names for a given role, in declaration order.

        Args:
            role: The FieldRole to filter by.

        Returns:
            List of column names with the specified role,
            in the order they appear in the roles dict.
        """
        return [col for col, r in self.roles.items() if r == role]


class Table(BaseModel):
    """Unified data carrier for algorithm I/O, visualization, and evaluation.

    A Table wraps a pandas DataFrame with a schema that assigns roles to columns.
    It provides accessors to retrieve columns by role and enforces schema constraints.

    Schema constraints (enforced on construction):
    - At least 1 METRIC column
    - At most 1 TIMESTAMP column
    - At most 1 LABEL column
    - All column names in roles must exist in df

    Attributes:
        df: The underlying pandas DataFrame.
        schema: The schema defining column roles (accessed via property).

    Note:
        Table returns copies of column data through accessors,
        preventing mutation of the underlying DataFrame.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    df: pd.DataFrame
    # Use PrivateAttr to store schema internally, avoiding field name conflict
    # with pydantic BaseModel's deprecated .schema() method
    _schema_data: TableSchema = PrivateAttr()

    def __init__(self, df: pd.DataFrame, schema: TableSchema, **data: object) -> None:
        """Initialize Table with df and schema.

        Args:
            df: The underlying pandas DataFrame (will be copied).
            schema: The schema defining column roles.
        """
        # Copy DataFrame to ensure immutability
        df_copy = df.copy()
        super().__init__(df=df_copy, **data)
        self._schema_data = schema
        # Run validation after setting schema
        self._validate_schema_constraints()

    @property
    def schema(self) -> TableSchema:  # type: ignore[override]
        """Get the schema defining column roles."""
        return self._schema_data

    def _validate_schema_constraints(self) -> None:
        """Validate schema constraints.

        Raises:
            SchemaValidationError: If schema constraints are violated.
        """
        # Check all role columns exist in df
        missing_cols = set(self._schema_data.roles.keys()) - set(self.df.columns)
        if missing_cols:
            raise SchemaValidationError(
                f"Columns in roles not found in DataFrame: {missing_cols}",
                context={"missing_columns": list(missing_cols)},
            )

        # Check METRIC constraint: at least 1
        metric_cols = self._schema_data.columns_of(FieldRole.METRIC)
        if len(metric_cols) < 1:
            raise SchemaValidationError(
                "Table must have at least 1 METRIC column",
                context={"metric_columns": metric_cols},
            )

        # Check TIMESTAMP constraint: at most 1
        timestamp_cols = self._schema_data.columns_of(FieldRole.TIMESTAMP)
        if len(timestamp_cols) > 1:
            raise SchemaValidationError(
                f"Table must have at most 1 TIMESTAMP column, found {len(timestamp_cols)}",
                context={"timestamp_columns": timestamp_cols},
            )

        # Check LABEL constraint: at most 1
        label_cols = self._schema_data.columns_of(FieldRole.LABEL)
        if len(label_cols) > 1:
            raise SchemaValidationError(
                f"Table must have at most 1 LABEL column, found {len(label_cols)}",
                context={"label_columns": label_cols},
            )

    def timestamps(self) -> pd.Series | None:
        """Get the TIMESTAMP column as a Series.

        Returns:
            The timestamp Series if a TIMESTAMP column exists, else None.
            Returns a copy to prevent mutation.
        """
        cols = self._schema_data.columns_of(FieldRole.TIMESTAMP)
        if not cols:
            return None
        return self.df[cols[0]].copy()

    def metrics(self) -> pd.DataFrame:
        """Get all METRIC columns as a DataFrame.

        Returns:
            DataFrame containing all METRIC columns.
            Returns a copy to prevent mutation.
        """
        cols = self._schema_data.columns_of(FieldRole.METRIC)
        return self.df[cols].copy()

    def labels(self) -> pd.Series | None:
        """Get the LABEL column as a Series.

        Returns:
            The label Series if a LABEL column exists, else None.
            Returns a copy to prevent mutation.
        """
        cols = self._schema_data.columns_of(FieldRole.LABEL)
        if not cols:
            return None
        return self.df[cols[0]].copy()
