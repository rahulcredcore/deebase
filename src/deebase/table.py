"""Table class for database table operations."""

from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING
from contextlib import asynccontextmanager
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker

from .column import ColumnAccessor
from .exceptions import (
    NotFoundError,
    IntegrityError as DeeBaseIntegrityError,
    ValidationError,
    SchemaError,
)
from .dataclass_utils import record_to_dict, dict_to_dataclass, make_table_dataclass

if TYPE_CHECKING:
    from .database import Database


class FKAccessor:
    """Accessor for foreign key navigation.

    Provides clean syntax for following foreign keys:
        author = await posts.fk.author_id(post)

    This is equivalent to the verbose API:
        author = await posts.get_parent(post, "author_id")
    """

    def __init__(self, table: "Table"):
        """Initialize the FKAccessor.

        Args:
            table: The Table instance this accessor belongs to
        """
        self._table = table

    def __getattr__(self, fk_column: str):
        """Return a callable for navigating via the specified FK column.

        Args:
            fk_column: Name of the foreign key column

        Returns:
            Async callable that takes a record and returns the parent
        """
        async def navigate(record: dict | Any) -> dict | Any | None:
            return await self._table.get_parent(record, fk_column)
        return navigate


class Table:
    """Represents a database table with CRUD operations.

    Supports both dict-based and dataclass-based operations.
    Return types depend on whether a dataclass is associated with the table.
    """

    def __init__(
        self,
        name: str,
        sa_table: sa.Table,
        engine: AsyncEngine,
        dataclass_cls: Optional[type] = None,
        xtra_filters: Optional[dict] = None,
        db: Optional["Database"] = None,
        foreign_keys: Optional[list[dict]] = None,
    ):
        """Initialize a Table.

        Args:
            name: Table name
            sa_table: SQLAlchemy Table object
            engine: AsyncEngine for database operations
            dataclass_cls: Optional dataclass for typed returns
            xtra_filters: Optional filters to apply to all operations
            db: Optional Database reference for FK navigation
            foreign_keys: Optional list of FK definitions
        """
        self._name = name
        self._sa_table = sa_table
        self._engine = engine
        self._dataclass_cls = dataclass_cls
        self._xtra_filters = xtra_filters or {}
        self._db = db
        self._foreign_keys = foreign_keys or []

    def _get_active_session(self) -> Optional[AsyncSession]:
        """Get the active transaction session if one exists."""
        from .database import _active_session
        return _active_session.get()

    @asynccontextmanager
    async def _session_scope(self):
        """Get a session - either active transaction or new managed session.

        If within a transaction context, yields the active session without
        committing/rolling back. Otherwise, creates a new session and manages
        its lifecycle.

        Yields:
            tuple[AsyncSession, bool] - (session, should_manage_lifecycle)
        """
        active_session = self._get_active_session()

        if active_session:
            # Within a transaction - use it, don't manage lifecycle
            yield active_session, False
        else:
            # No transaction - create and manage own session
            session_factory = sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            async with session_factory() as session:
                yield session, True

    @property
    def c(self) -> ColumnAccessor:
        """Access columns with auto-complete support."""
        return ColumnAccessor(self._sa_table)

    @property
    def schema(self) -> str:
        """Return the SQL schema definition for this table."""
        from sqlalchemy.schema import CreateTable
        return str(CreateTable(self._sa_table).compile(self._engine))

    @property
    def sa_table(self) -> sa.Table:
        """Expose the underlying SQLAlchemy Table object."""
        return self._sa_table

    @property
    def foreign_keys(self) -> list[dict]:
        """List of foreign key definitions for this table.

        Returns:
            List of dicts with 'column' and 'references' keys.

        Example:
            >>> posts.foreign_keys
            [{'column': 'author_id', 'references': 'users.id'}]
        """
        return self._foreign_keys.copy()

    @property
    def fk(self) -> FKAccessor:
        """Access foreign key navigation.

        Provides clean syntax for following foreign keys:
            author = await posts.fk.author_id(post)

        This is the convenience API. The equivalent power user API is:
            author = await posts.get_parent(post, "author_id")

        Returns:
            FKAccessor for FK navigation
        """
        return FKAccessor(self)

    def dataclass(self) -> type:
        """Generate or return the dataclass for this table.

        Once called, all subsequent operations will return dataclass instances
        instead of dicts.

        Returns:
            The dataclass type associated with this table
        """
        from dataclasses import is_dataclass

        # If _dataclass_cls is not set, or is set but not an actual dataclass,
        # generate a new dataclass from the table metadata
        if self._dataclass_cls is None or not is_dataclass(self._dataclass_cls):
            self._dataclass_cls = make_table_dataclass(self._name, self._sa_table)
        return self._dataclass_cls

    def xtra(self, **kwargs) -> "Table":
        """Return a new Table instance with additional filters.

        Filters apply to all subsequent operations (select, update, delete, insert).

        Args:
            **kwargs: Column=value filters

        Returns:
            New Table instance with filters applied
        """
        new_filters = {**self._xtra_filters, **kwargs}
        return Table(
            self._name,
            self._sa_table,
            self._engine,
            self._dataclass_cls,
            new_filters,
            self._db,
            self._foreign_keys,
        )

    async def insert(self, record: dict | Any) -> dict | Any:
        """Insert a record into the table.

        Args:
            record: Dict, dataclass, or object to insert

        Returns:
            Inserted record as dict or dataclass (depending on configuration)
        """
        # Convert input to dict
        data = self._from_input(record)

        # Validate xtra filters - ensure inserted record matches filters
        for col_name, expected_value in self._xtra_filters.items():
            if col_name in data and data[col_name] != expected_value:
                raise ValidationError(
                    f"Cannot insert into table '{self._name}': {col_name}={data[col_name]} violates filter {col_name}={expected_value}",
                    field=col_name,
                    value=data[col_name]
                )
            # If not provided, set the xtra filter value
            data[col_name] = expected_value

        # Execute INSERT and fetch the inserted record
        async with self._session_scope() as (session, should_manage):
            try:
                # Insert the record
                stmt = sa.insert(self._sa_table).values(**data)
                result = await session.execute(stmt)

                if should_manage:
                    await session.commit()

                # Get the inserted record's primary key
                inserted_pk = result.inserted_primary_key

                # Fetch the complete inserted record to get all values (including defaults)
                pk_cols = list(self._sa_table.primary_key.columns)
                if len(pk_cols) == 1:
                    # Single PK
                    select_stmt = sa.select(self._sa_table).where(
                        pk_cols[0] == inserted_pk[0]
                    )
                else:
                    # Composite PK
                    select_stmt = sa.select(self._sa_table)
                    for i, pk_col in enumerate(pk_cols):
                        select_stmt = select_stmt.where(pk_col == inserted_pk[i])

                fetch_result = await session.execute(select_stmt)
                row = fetch_result.fetchone()

                if row is None:
                    raise RuntimeError("Failed to fetch inserted record")

                return self._to_record(row)

            except sa.exc.IntegrityError as e:
                if should_manage:
                    await session.rollback()
                # Extract constraint name if available
                constraint = None
                error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
                if 'UNIQUE constraint' in error_msg or 'unique constraint' in error_msg.lower():
                    constraint = 'unique'
                elif 'PRIMARY KEY constraint' in error_msg or 'primary key' in error_msg.lower():
                    constraint = 'primary_key'
                elif 'FOREIGN KEY constraint' in error_msg or 'foreign key' in error_msg.lower():
                    constraint = 'foreign_key'

                raise DeeBaseIntegrityError(
                    f"Failed to insert into table '{self._name}': {error_msg}",
                    constraint=constraint,
                    table_name=self._name
                ) from e
            except Exception as e:
                if should_manage:
                    await session.rollback()
                raise RuntimeError(
                    f"Unexpected error inserting into table '{self._name}': {str(e)}"
                ) from e

    async def update(self, record: dict | Any) -> dict | Any:
        """Update a record in the table.

        Args:
            record: Dict, dataclass, or object with primary key to update

        Returns:
            Updated record as dict or dataclass

        Raises:
            NotFoundError: If record not found or violates xtra filters
        """
        # Convert input to dict
        data = self._from_input(record)

        # Extract primary key values from the record
        pk_cols = list(self._sa_table.primary_key.columns)
        pk_values = {}
        for pk_col in pk_cols:
            if pk_col.name not in data:
                raise ValidationError(
                    f"Cannot update table '{self._name}': primary key column '{pk_col.name}' missing from record",
                    field=pk_col.name
                )
            pk_values[pk_col.name] = data[pk_col.name]

        # Validate xtra filters
        for col_name, expected_value in self._xtra_filters.items():
            if col_name in data and data[col_name] != expected_value:
                raise ValidationError(
                    f"Cannot update table '{self._name}': {col_name}={data[col_name]} violates filter {col_name}={expected_value}",
                    field=col_name,
                    value=data[col_name]
                )

        # Execute UPDATE
        async with self._session_scope() as (session, should_manage):
            try:
                # Build WHERE clause for primary key(s)
                stmt = sa.update(self._sa_table)
                for pk_col in pk_cols:
                    stmt = stmt.where(pk_col == pk_values[pk_col.name])

                # Apply xtra filters to WHERE clause
                for col_name, value in self._xtra_filters.items():
                    stmt = stmt.where(self._sa_table.c[col_name] == value)

                # Set new values (excluding PK columns)
                update_data = {k: v for k, v in data.items() if k not in pk_values}
                stmt = stmt.values(**update_data)

                result = await session.execute(stmt)

                if should_manage:
                    await session.commit()

                # Check if any row was updated
                if result.rowcount == 0:
                    raise NotFoundError(
                        f"Record with PK {pk_values} not found in table '{self._name}' or violates xtra filters",
                        table_name=self._name,
                        filters={**pk_values, **self._xtra_filters}
                    )

                # Fetch and return the updated record
                select_stmt = sa.select(self._sa_table)
                for pk_col in pk_cols:
                    select_stmt = select_stmt.where(pk_col == pk_values[pk_col.name])

                fetch_result = await session.execute(select_stmt)
                row = fetch_result.fetchone()

                if row is None:
                    raise NotFoundError(
                        f"Record with PK {pk_values} not found in table '{self._name}' after update",
                        table_name=self._name,
                        filters=pk_values
                    )

                return self._to_record(row)

            except (NotFoundError, ValidationError):
                if should_manage:
                    await session.rollback()
                raise
            except sa.exc.IntegrityError as e:
                if should_manage:
                    await session.rollback()
                error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
                raise DeeBaseIntegrityError(
                    f"Failed to update table '{self._name}': {error_msg}",
                    table_name=self._name
                ) from e
            except Exception as e:
                if should_manage:
                    await session.rollback()
                raise RuntimeError(
                    f"Unexpected error updating table '{self._name}': {str(e)}"
                ) from e

    async def upsert(self, record: dict | Any) -> dict | Any:
        """Insert or update a record based on primary key existence.

        Args:
            record: Dict, dataclass, or object to upsert

        Returns:
            Upserted record as dict or dataclass
        """
        # Convert input to dict
        data = self._from_input(record)

        # Extract primary key values from the record
        pk_cols = list(self._sa_table.primary_key.columns)
        pk_values = {}
        has_pk = True
        for pk_col in pk_cols:
            if pk_col.name not in data or data[pk_col.name] is None:
                has_pk = False
                break
            pk_values[pk_col.name] = data[pk_col.name]

        # If no PK provided, just insert
        if not has_pk:
            return await self.insert(record)

        # Check if record exists
        async with self._session_scope() as (session, should_manage):
            try:
                # Build SELECT to check existence
                select_stmt = sa.select(self._sa_table)
                for pk_col in pk_cols:
                    select_stmt = select_stmt.where(pk_col == pk_values[pk_col.name])

                # Apply xtra filters
                for col_name, value in self._xtra_filters.items():
                    select_stmt = select_stmt.where(self._sa_table.c[col_name] == value)

                result = await session.execute(select_stmt)
                existing = result.fetchone()

                if should_manage:
                    await session.commit()

            except Exception:
                if should_manage:
                    await session.rollback()
                raise

        # If exists, update; otherwise, insert
        if existing:
            return await self.update(record)
        else:
            return await self.insert(record)

    async def delete(self, pk_value: Any) -> None:
        """Delete a record by primary key.

        Args:
            pk_value: Primary key value (or tuple for composite keys)

        Raises:
            NotFoundError: If record not found or violates xtra filters
        """
        # Get primary key columns
        pk_cols = list(self._sa_table.primary_key.columns)

        # Normalize pk_value to a tuple
        if len(pk_cols) == 1:
            pk_values = (pk_value,)
        else:
            if not isinstance(pk_value, (tuple, list)):
                raise ValidationError(
                    f"Composite primary key for table '{self._name}' requires tuple/list, got {type(pk_value).__name__}",
                    field='primary_key',
                    value=pk_value
                )
            pk_values = tuple(pk_value)

        if len(pk_values) != len(pk_cols):
            raise ValidationError(
                f"Primary key mismatch for table '{self._name}': expected {len(pk_cols)} values, got {len(pk_values)}",
                field='primary_key'
            )

        # Execute DELETE
        async with self._session_scope() as (session, should_manage):
            try:
                # Build DELETE statement with WHERE clause
                stmt = sa.delete(self._sa_table)
                for i, pk_col in enumerate(pk_cols):
                    stmt = stmt.where(pk_col == pk_values[i])

                # Apply xtra filters
                for col_name, value in self._xtra_filters.items():
                    stmt = stmt.where(self._sa_table.c[col_name] == value)

                result = await session.execute(stmt)

                if should_manage:
                    await session.commit()

                # Check if any row was deleted
                if result.rowcount == 0:
                    raise NotFoundError(
                        f"Record with PK {pk_value} not found in table '{self._name}' or violates xtra filters",
                        table_name=self._name,
                        filters={**dict(zip([col.name for col in pk_cols], pk_values)), **self._xtra_filters}
                    )

            except (NotFoundError, ValidationError):
                if should_manage:
                    await session.rollback()
                raise
            except Exception as e:
                if should_manage:
                    await session.rollback()
                raise RuntimeError(
                    f"Unexpected error deleting from table '{self._name}': {str(e)}"
                ) from e

    async def lookup(self, **kwargs) -> dict | Any:
        """Find a single record matching the given criteria.

        Args:
            **kwargs: Column=value filters

        Returns:
            Single record as dict or dataclass

        Raises:
            NotFoundError: If no record matches
        """
        if not kwargs:
            raise ValidationError("lookup() requires at least one filter argument")

        # Execute SELECT with WHERE
        async with self._session_scope() as (session, should_manage):
            try:
                # Build SELECT statement
                stmt = sa.select(self._sa_table)

                # Apply lookup filters
                for col_name, value in kwargs.items():
                    if col_name not in self._sa_table.c:
                        raise SchemaError(
                            f"Column '{col_name}' not found in table '{self._name}'",
                            table_name=self._name,
                            column_name=col_name
                        )
                    stmt = stmt.where(self._sa_table.c[col_name] == value)

                # Apply xtra filters
                for col_name, value in self._xtra_filters.items():
                    stmt = stmt.where(self._sa_table.c[col_name] == value)

                result = await session.execute(stmt)
                row = result.fetchone()

                if should_manage:
                    await session.commit()

                if row is None:
                    raise NotFoundError(
                        f"No record found in table '{self._name}' matching {kwargs}",
                        table_name=self._name,
                        filters={**kwargs, **self._xtra_filters}
                    )

                return self._to_record(row)

            except (NotFoundError, ValidationError, SchemaError):
                if should_manage:
                    await session.rollback()
                raise
            except Exception as e:
                if should_manage:
                    await session.rollback()
                raise RuntimeError(
                    f"Unexpected error in lookup on table '{self._name}': {str(e)}"
                ) from e

    async def __call__(
        self,
        limit: Optional[int] = None,
        with_pk: bool = False
    ) -> list[dict | Any]:
        """Select records from the table.

        Args:
            limit: Optional limit on number of records
            with_pk: If True, return tuples of (pk_value, record)

        Returns:
            List of records as dicts or dataclasses
        """
        # Execute SELECT
        async with self._session_scope() as (session, should_manage):
            try:
                # Build SELECT statement
                stmt = sa.select(self._sa_table)

                # Apply xtra filters
                for col_name, value in self._xtra_filters.items():
                    stmt = stmt.where(self._sa_table.c[col_name] == value)

                # Apply limit if specified
                if limit is not None:
                    stmt = stmt.limit(limit)

                result = await session.execute(stmt)
                rows = result.fetchall()

                if should_manage:
                    await session.commit()

                # Convert rows to records
                if with_pk:
                    # Return tuples of (pk_value, record)
                    pk_cols = list(self._sa_table.primary_key.columns)
                    records = []
                    for row in rows:
                        record = self._to_record(row)
                        # Extract PK value(s)
                        if len(pk_cols) == 1:
                            pk_value = row._mapping[pk_cols[0].name]
                        else:
                            pk_value = tuple(row._mapping[pk_col.name] for pk_col in pk_cols)
                        records.append((pk_value, record))
                    return records
                else:
                    return [self._to_record(row) for row in rows]

            except Exception:
                if should_manage:
                    await session.rollback()
                raise

    async def __getitem__(self, pk_value: Any) -> dict | Any:
        """Get a record by primary key.

        Args:
            pk_value: Primary key value (or tuple for composite keys)

        Returns:
            Record as dict or dataclass

        Raises:
            NotFoundError: If record not found
        """
        # Get primary key columns
        pk_cols = list(self._sa_table.primary_key.columns)

        # If no PK (e.g., views), use first column as pseudo-key
        if not pk_cols:
            pk_cols = [list(self._sa_table.columns)[0]]

        # Normalize pk_value to a tuple
        if len(pk_cols) == 1:
            pk_values = (pk_value,)
        else:
            if not isinstance(pk_value, (tuple, list)):
                raise ValidationError(
                    f"Composite primary key for table '{self._name}' requires tuple/list, got {type(pk_value).__name__}",
                    field='primary_key',
                    value=pk_value
                )
            pk_values = tuple(pk_value)

        if len(pk_values) != len(pk_cols):
            raise ValidationError(
                f"Primary key mismatch for table '{self._name}': expected {len(pk_cols)} values, got {len(pk_values)}",
                field='primary_key'
            )

        # Execute SELECT
        async with self._session_scope() as (session, should_manage):
            try:
                # Build SELECT statement
                stmt = sa.select(self._sa_table)
                for i, pk_col in enumerate(pk_cols):
                    stmt = stmt.where(pk_col == pk_values[i])

                # Apply xtra filters
                for col_name, value in self._xtra_filters.items():
                    stmt = stmt.where(self._sa_table.c[col_name] == value)

                result = await session.execute(stmt)
                row = result.fetchone()

                if should_manage:
                    await session.commit()

                if row is None:
                    raise NotFoundError(
                        f"Record with PK {pk_value} not found in table '{self._name}'",
                        table_name=self._name,
                        filters=dict(zip([col.name for col in pk_cols], pk_values))
                    )

                return self._to_record(row)

            except (NotFoundError, ValidationError):
                if should_manage:
                    await session.rollback()
                raise
            except Exception as e:
                if should_manage:
                    await session.rollback()
                raise RuntimeError(
                    f"Unexpected error fetching from table '{self._name}': {str(e)}"
                ) from e

    async def drop(self) -> None:
        """Drop the table from the database."""
        # Execute DROP TABLE
        async with self._session_scope() as (session, should_manage):
            try:
                await session.execute(sa.schema.DropTable(self._sa_table))
                if should_manage:
                    await session.commit()
            except Exception:
                if should_manage:
                    await session.rollback()
                raise

    async def transform(self, **kwargs) -> None:
        """Transform the table structure.

        Args:
            **kwargs: Transformation parameters
        """
        # TODO: Implement in Phase 8
        raise NotImplementedError("transform() will be implemented in Phase 8")

    @property
    def indexes(self) -> list[dict]:
        """List of indexes on this table.

        Returns:
            List of dicts with 'name', 'columns', and 'unique' keys.

        Example:
            >>> articles.indexes
            [{'name': 'ix_article_title', 'columns': ['title'], 'unique': False}]
        """
        result = []
        for index in self._sa_table.indexes:
            result.append({
                'name': index.name,
                'columns': [col.name for col in index.columns],
                'unique': index.unique
            })
        return result

    async def create_index(
        self,
        columns: str | list[str],
        name: Optional[str] = None,
        unique: bool = False
    ) -> None:
        """Create an index on the table.

        Args:
            columns: Column name (str) or list of column names for composite index
            name: Index name. Auto-generated if not provided.
            unique: If True, create a unique index

        Example:
            >>> await articles.create_index("title")
            >>> await articles.create_index(["author_id", "created_at"], name="idx_author_date")
            >>> await articles.create_index("email", unique=True)

        Raises:
            ValidationError: If column doesn't exist in table
        """
        # Normalize columns to list
        if isinstance(columns, str):
            columns = [columns]

        # Validate columns exist
        for col_name in columns:
            if col_name not in self._sa_table.c:
                raise ValidationError(
                    f"Column '{col_name}' not found in table '{self._name}'",
                    field=col_name
                )

        # Auto-generate name if not provided
        if name is None:
            name = f"ix_{self._name}_{'_'.join(columns)}"

        # Get SQLAlchemy column objects
        sa_columns = [self._sa_table.c[col_name] for col_name in columns]

        # Create and execute the index
        sa_index = sa.Index(name, *sa_columns, unique=unique)

        async with self._session_scope() as (session, should_manage):
            try:
                await session.execute(sa.schema.CreateIndex(sa_index))
                if should_manage:
                    await session.commit()
            except Exception:
                if should_manage:
                    await session.rollback()
                raise

    async def drop_index(self, name: str) -> None:
        """Drop an index from the table.

        Args:
            name: Name of the index to drop

        Example:
            >>> await articles.drop_index("idx_author_date")

        Note:
            Uses DROP INDEX syntax. The index must exist.
        """
        async with self._session_scope() as (session, should_manage):
            try:
                # Use raw SQL for DROP INDEX as SQLAlchemy doesn't have a direct DDL
                await session.execute(sa.text(f"DROP INDEX {name}"))
                if should_manage:
                    await session.commit()
            except Exception:
                if should_manage:
                    await session.rollback()
                raise

    async def get_parent(self, record: dict | Any, fk_column: str) -> dict | Any | None:
        """Navigate to parent record via a foreign key column.

        This is the power user API for FK navigation. For convenience, use:
            author = await posts.fk.author_id(post)

        Args:
            record: The record containing the FK value (dict or dataclass)
            fk_column: Name of the FK column in this table

        Returns:
            Parent record as dict or dataclass (respecting target table's setting),
            or None if FK value is None or parent not found.

        Raises:
            ValidationError: If fk_column doesn't exist or isn't an FK
            SchemaError: If referenced table not found in cache

        Example:
            >>> post = await posts[1]
            >>> author = await posts.get_parent(post, "author_id")
            >>> if author:
            ...     print(author['name'])
        """
        # Convert record to dict for consistent access
        data = self._from_input(record)

        # Validate FK column exists
        if fk_column not in self._sa_table.c:
            raise ValidationError(
                f"Column '{fk_column}' not found in table '{self._name}'",
                field=fk_column
            )

        # Find FK definition for this column
        fk_def = None
        for fk in self._foreign_keys:
            if fk['column'] == fk_column:
                fk_def = fk
                break

        if fk_def is None:
            raise ValidationError(
                f"Column '{fk_column}' is not a foreign key in table '{self._name}'",
                field=fk_column
            )

        # Get FK value from record
        fk_value = data.get(fk_column)

        # If FK value is None (nullable FK), return None
        if fk_value is None:
            return None

        # Parse the reference (format: "table.column")
        ref_parts = fk_def['references'].split('.')
        ref_table = ref_parts[0]
        ref_column = ref_parts[1] if len(ref_parts) > 1 else 'id'

        # Get the referenced table from db cache
        if self._db is None:
            raise SchemaError(
                f"Cannot navigate FK: Database reference not set for table '{self._name}'",
                table_name=self._name
            )

        parent_table = self._db._get_table(ref_table)
        if parent_table is None:
            raise SchemaError(
                f"Referenced table '{ref_table}' not found in cache. "
                f"Use 'await db.reflect_table(\"{ref_table}\")' to load it.",
                table_name=ref_table
            )

        # Fetch the parent record
        # Note: We assume the FK points to the PK of the parent table
        # For composite PKs, this would need enhancement
        try:
            return await parent_table[fk_value]
        except NotFoundError:
            # Parent not found (dangling FK) - return None per design decision
            return None

    async def get_children(
        self,
        record: dict | Any,
        child_table: str | "Table",
        fk_column: str
    ) -> list[dict | Any]:
        """Find child records that reference this record via a foreign key.

        This is the power user API for reverse FK navigation.

        Args:
            record: The parent record (dict or dataclass)
            child_table: Child table name (string) or Table object
            fk_column: Name of the FK column in the child table

        Returns:
            List of child records (may be empty if no children found).
            Respects child table's dataclass setting.

        Raises:
            SchemaError: If child table not found in cache
            ValidationError: If PK cannot be extracted from record

        Example:
            >>> user = await users[1]
            >>> user_posts = await users.get_children(user, "post", "author_id")
            >>> # Or with Table object:
            >>> user_posts = await users.get_children(user, posts, "author_id")
        """
        # Convert record to dict for consistent access
        data = self._from_input(record)

        # Get this table's primary key value
        pk_cols = list(self._sa_table.primary_key.columns)
        if not pk_cols:
            raise ValidationError(
                f"Table '{self._name}' has no primary key, cannot navigate to children",
                field='primary_key'
            )

        # Extract PK value(s)
        if len(pk_cols) == 1:
            pk_value = data.get(pk_cols[0].name)
        else:
            pk_value = tuple(data.get(pk_col.name) for pk_col in pk_cols)

        if pk_value is None or (isinstance(pk_value, tuple) and None in pk_value):
            raise ValidationError(
                f"Cannot extract primary key from record for table '{self._name}'",
                field='primary_key'
            )

        # Resolve child_table if it's a string
        if isinstance(child_table, str):
            if self._db is None:
                raise SchemaError(
                    f"Cannot navigate to children: Database reference not set for table '{self._name}'",
                    table_name=self._name
                )
            resolved_table = self._db._get_table(child_table)
            if resolved_table is None:
                raise SchemaError(
                    f"Child table '{child_table}' not found in cache. "
                    f"Use 'await db.reflect_table(\"{child_table}\")' to load it.",
                    table_name=child_table
                )
        else:
            # It's already a Table object
            resolved_table = child_table

        # Validate FK column exists in child table
        if fk_column not in resolved_table._sa_table.c:
            raise ValidationError(
                f"Column '{fk_column}' not found in table '{resolved_table._name}'",
                field=fk_column
            )

        # Query child table where fk_column = our PK value
        async with resolved_table._session_scope() as (session, should_manage):
            try:
                stmt = sa.select(resolved_table._sa_table).where(
                    resolved_table._sa_table.c[fk_column] == pk_value
                )

                result = await session.execute(stmt)
                rows = result.fetchall()

                if should_manage:
                    await session.commit()

                return [resolved_table._to_record(row) for row in rows]

            except Exception:
                if should_manage:
                    await session.rollback()
                raise

    def _to_dict(self, row: sa.Row) -> dict:
        """Convert a SQLAlchemy Row to a dict."""
        return dict(row._mapping)

    def _to_record(self, row: sa.Row) -> dict | Any:
        """Convert a SQLAlchemy Row to dict or dataclass based on configuration."""
        from dataclasses import is_dataclass

        data = self._to_dict(row)
        # Only convert to dataclass if the class is actually a dataclass
        if self._dataclass_cls and is_dataclass(self._dataclass_cls):
            return dict_to_dataclass(data, self._dataclass_cls)
        return data

    def _from_input(self, record: Any) -> dict:
        """Convert input record (dict, dataclass, or object) to dict."""
        return record_to_dict(record)

    def _apply_xtra(self, stmt: sa.sql.Select) -> sa.sql.Select:
        """Apply xtra filters to a SELECT statement."""
        for col_name, value in self._xtra_filters.items():
            stmt = stmt.where(self._sa_table.c[col_name] == value)
        return stmt

    def __getattr__(self, name: str):
        """Dispatch unknown attributes to the underlying SQLAlchemy table."""
        return getattr(self._sa_table, name)
