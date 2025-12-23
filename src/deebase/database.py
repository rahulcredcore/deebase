"""Database class for async database operations."""

from typing import Optional, Any
from contextlib import asynccontextmanager
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker

from .table import Table
from .view import View
from .types import python_type_to_sqlalchemy, is_optional
from .dataclass_utils import extract_annotations


class Database:
    """Main database interface for async SQLAlchemy operations.

    Attributes:
        engine: The underlying AsyncEngine
        t: Dynamic table accessor
        v: Dynamic view accessor
    """

    def __init__(self, url: str):
        """Initialize a Database connection.

        Args:
            url: Database URL (e.g., 'sqlite+aiosqlite:///mydb.db' or
                'postgresql+asyncpg://user:pass@localhost/dbname')
        """
        self._url = url
        self._engine = create_async_engine(url, echo=False)
        self._metadata = sa.MetaData()
        self._tables: dict[str, Table] = {}
        self._views: dict[str, View] = {}

        # Session factory
        self._session_factory = sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Dynamic accessors
        self.t = TableAccessor(self)
        self.v = ViewAccessor(self)

    @property
    def engine(self) -> AsyncEngine:
        """Expose the underlying SQLAlchemy AsyncEngine."""
        return self._engine

    @asynccontextmanager
    async def _session(self):
        """Create an async session context manager.

        Yields:
            AsyncSession for database operations
        """
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def q(self, query: str) -> list[dict]:
        """Execute a raw SQL query and return results as dicts.

        Args:
            query: SQL query string

        Returns:
            List of dictionaries representing rows (empty list for DDL/DML)
        """
        async with self._session() as session:
            result = await session.execute(sa.text(query))
            # Check if the result returns rows (SELECT) or not (CREATE, INSERT, etc.)
            if result.returns_rows:
                return [dict(row._mapping) for row in result.fetchall()]
            return []

    async def create(
        self,
        cls: type,
        pk: Optional[str | list[str]] = None
    ) -> Table:
        """Create a table from a Python class with type annotations.

        Args:
            cls: Class with type annotations defining the schema
            pk: Primary key column name(s). If None, uses 'id' by default.

        Returns:
            Table instance for the created table

        Examples:
            >>> class User:
            ...     id: int
            ...     name: str
            ...     email: str
            >>> users = await db.create(User, pk='id')
        """
        from .dataclass_utils import extract_annotations
        from .types import python_type_to_sqlalchemy, is_optional

        # Get table name from class name (lowercase)
        table_name = cls.__name__.lower()

        # Extract type annotations from the class
        annotations = extract_annotations(cls)

        if not annotations:
            raise ValueError(f"Class {cls.__name__} has no type annotations")

        # Determine primary key(s)
        if pk is None:
            pk = 'id'

        # Normalize pk to a list for uniform handling
        pk_list = [pk] if isinstance(pk, str) else pk

        # Verify all pk columns exist in annotations
        for pk_col in pk_list:
            if pk_col not in annotations:
                raise ValueError(f"Primary key column '{pk_col}' not found in class annotations")

        # Build SQLAlchemy columns
        columns = []
        for field_name, field_type in annotations.items():
            # Determine if nullable
            nullable = is_optional(field_type)

            # Get SQLAlchemy type
            sa_type = python_type_to_sqlalchemy(field_type)

            # Check if this is a primary key column
            is_pk = field_name in pk_list

            # Create column (PKs are not nullable unless explicitly Optional)
            col = sa.Column(
                field_name,
                sa_type,
                primary_key=is_pk,
                nullable=nullable and not is_pk
            )
            columns.append(col)

        # Create SQLAlchemy Table
        sa_table = sa.Table(
            table_name,
            self._metadata,
            *columns
        )

        # Execute CREATE TABLE
        async with self._session() as session:
            await session.execute(sa.schema.CreateTable(sa_table))

        # Create Table instance with the class as the dataclass
        table_instance = Table(
            table_name,
            sa_table,
            self._engine,
            dataclass_cls=cls
        )

        # Cache the table
        self._cache_table(table_name, table_instance)

        return table_instance

    async def create_view(
        self,
        name: str,
        sql: str,
        replace: bool = False
    ) -> View:
        """Create a database view.

        Args:
            name: View name
            sql: SQL query defining the view
            replace: If True, replace existing view

        Returns:
            View instance for the created view
        """
        # TODO: Implement in Phase 7
        raise NotImplementedError("create_view() will be implemented in Phase 7")

    async def import_file(
        self,
        table_name: str,
        file: str,
        format: Optional[str] = None,
        pk: Optional[str | list[str]] = None,
        alter: bool = False
    ) -> Table:
        """Import data from a file to a new table.

        Args:
            table_name: Name for the new table
            file: File path to import
            format: File format (csv, json, etc.). Auto-detected if None.
            pk: Primary key column name(s)
            alter: If True, alter existing table to match

        Returns:
            Table instance for the created/updated table
        """
        # TODO: Implement in Phase 8
        raise NotImplementedError("import_file() will be implemented in Phase 8")

    def _get_table(self, name: str) -> Optional[Table]:
        """Get a cached table by name.

        Args:
            name: Table name

        Returns:
            Cached Table instance or None
        """
        return self._tables.get(name)

    def _cache_table(self, name: str, table: Table) -> None:
        """Cache a table instance.

        Args:
            name: Table name
            table: Table instance to cache
        """
        self._tables[name] = table

    async def close(self) -> None:
        """Close the database connection and dispose of the engine."""
        await self._engine.dispose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


class TableAccessor:
    """Dynamic accessor for database tables.

    Supports both attribute and index access:
        db.t.users
        db.t['users']
        db.t['users', 'posts']  # Multiple tables
    """

    def __init__(self, db: Database):
        """Initialize the TableAccessor.

        Args:
            db: Database instance
        """
        self._db = db

    def __getattr__(self, name: str) -> Table:
        """Access a table by attribute name.

        Args:
            name: Table name

        Returns:
            Table instance
        """
        # TODO: Implement reflection in Phase 5
        raise NotImplementedError("Table reflection will be implemented in Phase 5")

    def __getitem__(self, key: str | tuple[str, ...]) -> Table | tuple[Table, ...]:
        """Access table(s) by index.

        Args:
            key: Table name or tuple of table names

        Returns:
            Single Table or tuple of Tables
        """
        if isinstance(key, tuple):
            return tuple(self.__getattr__(name) for name in key)
        return self.__getattr__(key)


class ViewAccessor:
    """Dynamic accessor for database views.

    Works similarly to TableAccessor but for views.
    """

    def __init__(self, db: Database):
        """Initialize the ViewAccessor.

        Args:
            db: Database instance
        """
        self._db = db

    def __getattr__(self, name: str) -> View:
        """Access a view by attribute name.

        Args:
            name: View name

        Returns:
            View instance
        """
        # TODO: Implement view reflection in Phase 7
        raise NotImplementedError("View reflection will be implemented in Phase 7")

    def __getitem__(self, key: str | tuple[str, ...]) -> View | tuple[View, ...]:
        """Access view(s) by index.

        Args:
            key: View name or tuple of view names

        Returns:
            Single View or tuple of Views
        """
        if isinstance(key, tuple):
            return tuple(self.__getattr__(name) for name in key)
        return self.__getattr__(key)
