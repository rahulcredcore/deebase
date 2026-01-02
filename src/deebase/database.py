"""Database class for async database operations."""

from typing import Optional, Any
from contextlib import asynccontextmanager
from contextvars import ContextVar
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker

from .table import Table
from .view import View
from .types import python_type_to_sqlalchemy, is_optional, Index
from .dataclass_utils import extract_annotations
from .exceptions import (
    ConnectionError as DeeBaseConnectionError,
    SchemaError,
    ValidationError,
)

# Context variable to store the active transaction session
_active_session: ContextVar[Optional[AsyncSession]] = ContextVar('_active_session', default=None)


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

    @asynccontextmanager
    async def transaction(self):
        """Context manager for multi-operation transactions.

        All CRUD operations within this context will participate in a single
        transaction that commits on success or rolls back on exception.

        Yields:
            AsyncSession for the transaction

        Example:
            >>> async with db.transaction():
            ...     await users.insert({"name": "Alice"})
            ...     await users.insert({"name": "Bob"})
            ...     # Both inserts commit together
        """
        async with self._session_factory() as session:
            token = _active_session.set(session)
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                _active_session.reset(token)

    async def q(self, query: str) -> list[dict]:
        """Execute a raw SQL query and return results as dicts.

        Args:
            query: SQL query string

        Returns:
            List of dictionaries representing rows (empty list for DDL/DML)
        """
        try:
            async with self._session() as session:
                result = await session.execute(sa.text(query))
                # Check if the result returns rows (SELECT) or not (CREATE, INSERT, etc.)
                if result.returns_rows:
                    return [dict(row._mapping) for row in result.fetchall()]
                return []
        except sa.exc.OperationalError as e:
            # Connection errors, database not found, etc.
            error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
            raise DeeBaseConnectionError(
                f"Database connection error: {error_msg}",
                database_url=self._url.split('@')[-1] if '@' in self._url else self._url.split(':///')[-1]
            ) from e
        except sa.exc.ProgrammingError as e:
            # SQL syntax errors, table not found, etc.
            error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
            raise SchemaError(
                f"SQL error: {error_msg}"
            ) from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error executing query: {str(e)}") from e

    async def create(
        self,
        cls: type,
        pk: Optional[str | list[str]] = None,
        if_not_exists: bool = False,
        replace: bool = False,
        indexes: Optional[list[str | tuple[str, ...] | Index]] = None,
    ) -> Table:
        """Create a table from a Python class with type annotations.

        Args:
            cls: Class with type annotations defining the schema
            pk: Primary key column name(s). If None, uses 'id' by default.
            if_not_exists: If True, don't error if table already exists
            replace: If True, drop existing table before creating
            indexes: List of indexes to create. Each item can be:
                - str: Single column index with auto-generated name
                - tuple: Composite index with auto-generated name
                - Index: Named index with optional unique constraint

        Returns:
            Table instance for the created table

        Examples:
            >>> class User:
            ...     id: int
            ...     name: str
            ...     status: str = "active"  # Default value
            >>> users = await db.create(User, pk='id')

            >>> from deebase import ForeignKey, Index
            >>> class Post:
            ...     id: int
            ...     author_id: ForeignKey[int, "user"]  # FK to user.id
            ...     title: str
            >>> posts = await db.create(Post, pk='id', indexes=[
            ...     "title",                                # Simple index
            ...     ("author_id", "created_at"),            # Composite index
            ...     Index("idx_title_unique", "title", unique=True),  # Named unique index
            ... ])
        """
        from .dataclass_utils import extract_annotations, extract_defaults
        from .types import python_type_to_sqlalchemy, is_optional, is_foreign_key, get_foreign_key_info

        # Get table name from class name (lowercase)
        table_name = cls.__name__.lower()

        # Handle replace - drop table first
        if replace:
            async with self._session() as session:
                await session.execute(sa.text(f"DROP TABLE IF EXISTS {table_name}"))
            # Remove from metadata if it exists
            if table_name in self._metadata.tables:
                self._metadata.remove(self._metadata.tables[table_name])
            # Remove from cache
            self._tables.pop(table_name, None)

        # Extract type annotations from the class
        annotations = extract_annotations(cls)

        if not annotations:
            raise ValidationError(
                f"Class {cls.__name__} has no type annotations. Cannot create table without field definitions."
            )

        # Extract default values
        defaults = extract_defaults(cls)

        # Determine primary key(s)
        if pk is None:
            pk = 'id'

        # Normalize pk to a list for uniform handling
        pk_list = [pk] if isinstance(pk, str) else pk

        # Verify all pk columns exist in annotations
        for pk_col in pk_list:
            if pk_col not in annotations:
                raise SchemaError(
                    f"Primary key column '{pk_col}' not found in class {cls.__name__} annotations",
                    table_name=cls.__name__.lower(),
                    column_name=pk_col
                )

        # Build SQLAlchemy columns and collect foreign keys
        columns = []
        foreign_keys = []  # List of (column_name, other_table, other_column)

        for field_name, field_type in annotations.items():
            # Check if this is a ForeignKey type
            if is_foreign_key(field_type):
                base_type, other_table, other_column = get_foreign_key_info(field_type)
                foreign_keys.append((field_name, other_table, other_column))
                # Use the base type for the column
                sa_type = python_type_to_sqlalchemy(base_type)
                nullable = False  # FKs typically not nullable
            else:
                # Determine if nullable
                nullable = is_optional(field_type)
                # Get SQLAlchemy type
                sa_type = python_type_to_sqlalchemy(field_type)

            # Check if this is a primary key column
            is_pk = field_name in pk_list

            # Get default value if any
            server_default = None
            if field_name in defaults:
                default_val = defaults[field_name]
                # Convert to string for server_default
                if isinstance(default_val, str):
                    server_default = sa.text(f"'{default_val}'")
                elif isinstance(default_val, bool):
                    # SQLite uses 0/1 for booleans
                    server_default = sa.text('1' if default_val else '0')
                else:
                    server_default = sa.text(str(default_val))

            # Create column (PKs are not nullable unless explicitly Optional)
            col = sa.Column(
                field_name,
                sa_type,
                primary_key=is_pk,
                nullable=nullable and not is_pk,
                server_default=server_default
            )
            columns.append(col)

        # Add foreign key constraints
        fk_constraints = []
        for col_name, other_table, other_column in foreign_keys:
            fk_constraints.append(
                sa.ForeignKeyConstraint(
                    [col_name],
                    [f"{other_table}.{other_column}"]
                )
            )

        # Build FK metadata list for the Table (needed for both new and existing)
        fk_metadata = [
            {'column': col_name, 'references': f"{other_table}.{other_column}"}
            for col_name, other_table, other_column in foreign_keys
        ]

        # Check if table already exists in metadata
        if table_name in self._metadata.tables:
            if if_not_exists:
                # Return existing table
                existing_table = self._metadata.tables[table_name]
                table_instance = Table(
                    table_name,
                    existing_table,
                    self._engine,
                    dataclass_cls=cls,
                    db=self,
                    foreign_keys=fk_metadata,
                )
                self._cache_table(table_name, table_instance)
                return table_instance
            else:
                # Remove from metadata so we can recreate (will fail at DB level if exists)
                self._metadata.remove(self._metadata.tables[table_name])

        # Create SQLAlchemy Table
        sa_table = sa.Table(
            table_name,
            self._metadata,
            *columns,
            *fk_constraints
        )

        # Execute CREATE TABLE
        async with self._session() as session:
            try:
                if if_not_exists:
                    # Use CREATE TABLE IF NOT EXISTS syntax
                    create_stmt = sa.schema.CreateTable(sa_table, if_not_exists=True)
                    await session.execute(create_stmt)
                else:
                    await session.execute(sa.schema.CreateTable(sa_table))
            except sa.exc.OperationalError as e:
                # Table might already exist
                if 'already exists' in str(e).lower() and not if_not_exists:
                    raise SchemaError(
                        f"Table '{table_name}' already exists. Use if_not_exists=True or replace=True.",
                        table_name=table_name
                    ) from e
                raise

        # Create indexes if specified
        if indexes:
            await self._create_indexes(table_name, sa_table, indexes, annotations)

        # Create Table instance with the class as the dataclass
        # (fk_metadata was built earlier, before the if_not_exists check)
        table_instance = Table(
            table_name,
            sa_table,
            self._engine,
            dataclass_cls=cls,
            db=self,
            foreign_keys=fk_metadata,
        )

        # Cache the table
        self._cache_table(table_name, table_instance)

        return table_instance

    async def reflect(self, schema: Optional[str] = None) -> None:
        """Reflect all tables from the database into cache.

        This scans the database and loads all existing table schemas,
        making them available via db.t.tablename.

        Args:
            schema: Optional schema name (for databases that support schemas)

        Example:
            >>> db = Database("sqlite+aiosqlite:///myapp.db")
            >>> await db.reflect()
            >>> users = db.t.users  # Now works (cache hit)
        """
        # Reflect into self._metadata so FK references work when creating new tables
        async with self._engine.connect() as conn:
            await conn.run_sync(self._metadata.reflect)

        # Wrap each reflected table and cache it
        for table_name, sa_table in self._metadata.tables.items():
            # Skip if already cached (e.g., from db.create())
            if table_name not in self._tables:
                # Extract FK metadata from SQLAlchemy reflection
                fk_metadata = self._extract_fk_metadata(sa_table)
                # Create Table instance without dataclass (returns dicts by default)
                table = Table(table_name, sa_table, self._engine, db=self, foreign_keys=fk_metadata)
                self._cache_table(table_name, table)

    async def reflect_table(self, name: str) -> Table:
        """Reflect a specific table from the database.

        Args:
            name: Table name to reflect

        Returns:
            Table instance for the reflected table

        Example:
            >>> products = await db.reflect_table('products')
            >>> # Now db.t.products also works
        """
        # Check if already cached
        if cached := self._get_table(name):
            return cached

        # Reflect just this table
        async with self._engine.connect() as conn:
            # Use run_sync to reflect the table
            def _reflect_table(sync_conn):
                reflect_metadata = sa.MetaData()
                sa_table = sa.Table(name, reflect_metadata, autoload_with=sync_conn)
                return sa_table

            sa_table = await conn.run_sync(_reflect_table)

        # Extract FK metadata from SQLAlchemy reflection
        fk_metadata = self._extract_fk_metadata(sa_table)

        # Wrap and cache
        table = Table(name, sa_table, self._engine, db=self, foreign_keys=fk_metadata)
        self._cache_table(name, table)

        return table

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

        Example:
            >>> view = await db.create_view(
            ...     "active_users",
            ...     "SELECT * FROM users WHERE active = 1"
            ... )
        """
        # Drop existing view if replace=True
        if replace:
            async with self._session() as session:
                try:
                    await session.execute(sa.text(f"DROP VIEW IF EXISTS {name}"))
                except Exception:
                    pass  # View might not exist

        # Create the view
        create_sql = f"CREATE VIEW {name} AS {sql}"
        async with self._session() as session:
            await session.execute(sa.text(create_sql))

        # Reflect the view to get its structure
        async with self._engine.connect() as conn:
            def _reflect_view(sync_conn):
                reflect_metadata = sa.MetaData()
                sa_table = sa.Table(name, reflect_metadata, autoload_with=sync_conn)
                return sa_table

            sa_table = await conn.run_sync(_reflect_view)

        # Create View instance
        view = View(name, sa_table, self._engine)

        # Cache the view
        self._views[name] = view

        return view

    async def reflect_view(self, name: str) -> View:
        """Reflect an existing view from the database.

        Args:
            name: View name to reflect

        Returns:
            View instance for the reflected view

        Example:
            >>> view = await db.reflect_view('active_users')
            >>> # Now db.v.active_users also works
        """
        # Check if already cached
        if cached := self._views.get(name):
            return cached

        # Reflect the view
        async with self._engine.connect() as conn:
            def _reflect_view(sync_conn):
                reflect_metadata = sa.MetaData()
                sa_table = sa.Table(name, reflect_metadata, autoload_with=sync_conn)
                return sa_table

            sa_table = await conn.run_sync(_reflect_view)

        # Create View instance
        view = View(name, sa_table, self._engine)

        # Cache the view
        self._views[name] = view

        return view

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

    def _extract_fk_metadata(self, sa_table: sa.Table) -> list[dict]:
        """Extract foreign key metadata from a SQLAlchemy Table.

        Args:
            sa_table: SQLAlchemy Table object

        Returns:
            List of FK definitions: [{'column': str, 'references': 'table.column'}, ...]
        """
        fk_metadata = []
        for fk in sa_table.foreign_keys:
            # fk.parent is the local column, fk.column is the referenced column
            local_col = fk.parent.name
            # fk.target_fullname gives us "table.column"
            ref_full = fk.target_fullname
            fk_metadata.append({
                'column': local_col,
                'references': ref_full
            })
        return fk_metadata

    async def _create_indexes(
        self,
        table_name: str,
        sa_table: sa.Table,
        indexes: list[str | tuple[str, ...] | Index],
        annotations: dict[str, type]
    ) -> None:
        """Create indexes on a table.

        Args:
            table_name: Name of the table
            sa_table: SQLAlchemy Table object
            indexes: List of index specifications
            annotations: Class annotations (for column validation)
        """
        for idx_spec in indexes:
            # Parse the index specification
            if isinstance(idx_spec, str):
                # Single column index with auto-generated name
                columns = [idx_spec]
                name = f"ix_{table_name}_{idx_spec}"
                unique = False
            elif isinstance(idx_spec, tuple):
                # Composite index with auto-generated name
                columns = list(idx_spec)
                name = f"ix_{table_name}_{'_'.join(columns)}"
                unique = False
            elif isinstance(idx_spec, Index):
                # Named index with options
                columns = idx_spec.columns
                name = idx_spec.name
                unique = idx_spec.unique
            else:
                raise ValidationError(
                    f"Invalid index specification: {idx_spec}. "
                    f"Expected str, tuple, or Index."
                )

            # Validate that columns exist
            for col_name in columns:
                if col_name not in annotations:
                    raise ValidationError(
                        f"Index column '{col_name}' not found in table '{table_name}'",
                        field=col_name
                    )

            # Get SQLAlchemy column objects
            sa_columns = [sa_table.c[col_name] for col_name in columns]

            # Create and execute the index
            sa_index = sa.Index(name, *sa_columns, unique=unique)
            async with self._session() as session:
                await session.execute(sa.schema.CreateIndex(sa_index))

    async def enable_foreign_keys(self) -> None:
        """Enable foreign key enforcement (SQLite only, no-op on PostgreSQL).

        SQLite has FK enforcement disabled by default. PostgreSQL always enforces FKs.
        Call this after creating a Database connection if using SQLite with FKs.

        This method is safe to call on any database - it's a no-op on databases
        that always enforce FKs (like PostgreSQL).

        Example:
            >>> db = Database("sqlite+aiosqlite:///app.db")
            >>> await db.enable_foreign_keys()
            >>> # Now FK constraints are enforced on SQLite

            >>> # Or use immediately after connection
            >>> async with Database("sqlite+aiosqlite:///app.db") as db:
            ...     await db.enable_foreign_keys()
            ...     # FK enforcement is now active
        """
        dialect_name = self._engine.dialect.name
        if dialect_name == "sqlite":
            await self.q("PRAGMA foreign_keys = ON")
        # PostgreSQL and other databases always enforce FKs, no action needed

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
        """Access a table by attribute name (cache-only, synchronous).

        Args:
            name: Table name

        Returns:
            Table instance from cache

        Raises:
            AttributeError: If table not in cache

        Example:
            >>> await db.reflect()
            >>> users = db.t.users  # Cache hit
        """
        # Check cache
        if table := self._db._get_table(name):
            return table

        # Not in cache - provide helpful error message
        raise AttributeError(
            f"Table '{name}' not found in cache. "
            f"Use 'await db.reflect()' to load all tables, "
            f"or 'await db.reflect_table(\"{name}\")' to load this specific table."
        )

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
        """Access a view by attribute name (cache-only, synchronous).

        Args:
            name: View name

        Returns:
            View instance from cache

        Raises:
            AttributeError: If view not in cache

        Example:
            >>> await db.create_view("active_users", "SELECT * FROM users WHERE active = 1")
            >>> view = db.v.active_users  # Cache hit
        """
        # Check cache
        if view := self._db._views.get(name):
            return view

        # Not in cache - provide helpful error message
        raise AttributeError(
            f"View '{name}' not found in cache. "
            f"Use 'await db.create_view(\"{name}\", sql)' to create it, "
            f"or 'await db.reflect_view(\"{name}\")' to load an existing view."
        )

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
