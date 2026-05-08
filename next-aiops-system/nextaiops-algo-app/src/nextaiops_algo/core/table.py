"""Table - unified data carrier for algorithm I/O."""

from enum import StrEnum
from typing import Self

import pandas as pd
from pydantic import BaseModel, Field, model_validator

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
        schema: The schema defining column roles.

    Note:
        Table returns copies of column data through accessors,
        preventing mutation of the underlying DataFrame.
    """

    df: pd.DataFrame
    _schema: TableSchema = Field(alias="schema")

    @property
    def schema(self) -> TableSchema:  # type: ignore[override]
        """Get the schema defining column roles."""
        return self._schema

    @model_validator(mode="after")
    def validate_schema(self) -> Self:
        """Validate schema constraints after model construction.

        Raises:
            SchemaValidationError: If schema constraints are violated.
        """
        # Check all role columns exist in df
        missing_cols = set(self._schema.roles.keys()) - set(self.df.columns)
        if missing_cols:
            raise SchemaValidationError(
                f"Columns in roles not found in DataFrame: {missing_cols}",
                context={"missing_columns": list(missing_cols)},
            )

        # Check METRIC constraint: at least 1
        metric_cols = self._schema.columns_of(FieldRole.METRIC)
        if len(metric_cols) < 1:
            raise SchemaValidationError(
                "Table must have at least 1 METRIC column",
                context={"metric_columns": metric_cols},
            )

        # Check TIMESTAMP constraint: at most 1
        timestamp_cols = self._schema.columns_of(FieldRole.TIMESTAMP)
        if len(timestamp_cols) > 1:
            raise SchemaValidationError(
                f"Table must have at most 1 TIMESTAMP column, found {len(timestamp_cols)}",
                context={"timestamp_columns": timestamp_cols},
            )

        # Check LABEL constraint: at most 1
        label_cols = self._schema.columns_of(FieldRole.LABEL)
        if len(label_cols) > 1:
            raise SchemaValidationError(
                f"Table must have at most 1 LABEL column, found {len(label_cols)}",
                context={"label_columns": label_cols},
            )

        return self

    def timestamps(self) -> pd.Series | None:
        """Get the TIMESTAMP column as a Series.

        Returns:
            The timestamp Series if a TIMESTAMP column exists, else None.
            Returns a copy to prevent mutation.
        """
        cols = self._schema.columns_of(FieldRole.TIMESTAMP)
        if not cols:
            return None
        return self.df[cols[0]].copy()

    def metrics(self) -> pd.DataFrame:
        """Get all METRIC columns as a DataFrame.

        Returns:
            DataFrame containing all METRIC columns.
            Returns a copy to prevent mutation.
        """
        cols = self._schema.columns_of(FieldRole.METRIC)
        return self.df[cols].copy()

    def labels(self) -> pd.Series | None:
        """Get the LABEL column as a Series.

        Returns:
            The label Series if a LABEL column exists, else None.
            Returns a copy to prevent mutation.
        """
        cols = self._schema.columns_of(FieldRole.LABEL)
        if not cols:
            return None
        return self.df[cols[0]].copy()
