"""Tests for Column and ColumnAccessor classes."""

import pytest
import sqlalchemy as sa

from deebase.column import Column, ColumnAccessor


class TestColumn:
    """Tests for Column class."""

    def test_column_creation(self):
        """Test creating a Column wrapper."""
        sa_col = sa.Column("name", sa.String)
        col = Column(sa_col)
        assert col.sa_column == sa_col

    def test_column_str(self):
        """Test SQL-safe stringification."""
        sa_col = sa.Column("user_name", sa.String)
        col = Column(sa_col)
        assert str(col) == '"user_name"'

    def test_column_repr(self):
        """Test column representation."""
        sa_col = sa.Column("id", sa.Integer)
        col = Column(sa_col)
        assert repr(col) == "Column('id')"

    def test_column_attribute_dispatch(self):
        """Test that unknown attributes dispatch to sa_column."""
        sa_col = sa.Column("id", sa.Integer, primary_key=True)
        col = Column(sa_col)
        # Access sa_column attribute through wrapper
        assert col.name == "id"
        assert col.primary_key is True


class TestColumnAccessor:
    """Tests for ColumnAccessor class."""

    def test_accessor_creation(self):
        """Test creating a ColumnAccessor."""
        metadata = sa.MetaData()
        table = sa.Table(
            "users",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String),
        )
        accessor = ColumnAccessor(table)
        assert accessor is not None

    def test_get_column_by_name(self):
        """Test accessing column by attribute name."""
        metadata = sa.MetaData()
        table = sa.Table(
            "users",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String),
        )
        accessor = ColumnAccessor(table)

        id_col = accessor.id
        assert isinstance(id_col, Column)
        assert id_col.sa_column.name == "id"

        name_col = accessor.name
        assert isinstance(name_col, Column)
        assert name_col.sa_column.name == "name"

    def test_nonexistent_column_raises_error(self):
        """Test accessing non-existent column raises AttributeError."""
        metadata = sa.MetaData()
        table = sa.Table(
            "users",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
        )
        accessor = ColumnAccessor(table)

        with pytest.raises(AttributeError, match="has no column 'nonexistent'"):
            _ = accessor.nonexistent

    def test_iterate_columns(self):
        """Test iterating over columns."""
        metadata = sa.MetaData()
        table = sa.Table(
            "users",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String),
            sa.Column("email", sa.String),
        )
        accessor = ColumnAccessor(table)

        columns = list(accessor)
        assert len(columns) == 3
        assert all(isinstance(col, Column) for col in columns)

        column_names = [col.sa_column.name for col in columns]
        assert column_names == ["id", "name", "email"]

    def test_dir_returns_column_names(self):
        """Test __dir__ returns column names for auto-complete."""
        metadata = sa.MetaData()
        table = sa.Table(
            "users",
            metadata,
            sa.Column("id", sa.Integer),
            sa.Column("name", sa.String),
        )
        accessor = ColumnAccessor(table)

        dir_result = dir(accessor)
        assert "id" in dir_result
        assert "name" in dir_result
