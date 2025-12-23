"""Column and ColumnAccessor classes for database column access."""

from typing import Iterator
import sqlalchemy as sa


class Column:
    """Wrapper for a SQLAlchemy Column with SQL-safe stringification.

    Attributes:
        sa_column: The underlying SQLAlchemy Column object
    """

    def __init__(self, sa_column: sa.Column):
        """Initialize a Column wrapper.

        Args:
            sa_column: SQLAlchemy Column to wrap
        """
        self.sa_column = sa_column

    def __str__(self) -> str:
        """Return SQL-safe quoted column name."""
        return f'"{self.sa_column.name}"'

    def __repr__(self) -> str:
        """Return string representation of the column."""
        return f"Column({self.sa_column.name!r})"

    def __getattr__(self, name: str):
        """Dispatch unknown attributes to the underlying SQLAlchemy column."""
        return getattr(self.sa_column, name)


class ColumnAccessor:
    """Provides dynamic access to table columns with auto-complete support.

    Allows accessing columns via attribute notation: table.c.column_name
    """

    def __init__(self, sa_table: sa.Table):
        """Initialize the ColumnAccessor.

        Args:
            sa_table: SQLAlchemy Table whose columns to provide access to
        """
        self._sa_table = sa_table

    def __getattr__(self, name: str) -> Column:
        """Get a column by name.

        Args:
            name: Column name

        Returns:
            Column wrapper

        Raises:
            AttributeError: If column doesn't exist
        """
        if name in self._sa_table.columns:
            return Column(self._sa_table.columns[name])
        raise AttributeError(f"Table {self._sa_table.name} has no column {name!r}")

    def __iter__(self) -> Iterator[Column]:
        """Iterate over all columns in the table.

        Yields:
            Column wrappers for each column in the table
        """
        for col in self._sa_table.columns:
            yield Column(col)

    def __dir__(self):
        """Return list of column names for auto-complete support."""
        return list(self._sa_table.columns.keys())
