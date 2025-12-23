"""Table class for database table operations."""

from typing import Any, Optional
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine

from .column import ColumnAccessor
from .exceptions import (
    NotFoundError,
    IntegrityError as DeeBaseIntegrityError,
    ValidationError,
    SchemaError,
)
from .dataclass_utils import record_to_dict, dict_to_dataclass, make_table_dataclass


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
        xtra_filters: Optional[dict] = None
    ):
        """Initialize a Table.

        Args:
            name: Table name
            sa_table: SQLAlchemy Table object
            engine: AsyncEngine for database operations
            dataclass_cls: Optional dataclass for typed returns
            xtra_filters: Optional filters to apply to all operations
        """
        self._name = name
        self._sa_table = sa_table
        self._engine = engine
        self._dataclass_cls = dataclass_cls
        self._xtra_filters = xtra_filters or {}

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
            new_filters
        )

    async def insert(self, record: dict | Any) -> dict | Any:
        """Insert a record into the table.

        Args:
            record: Dict, dataclass, or object to insert

        Returns:
            Inserted record as dict or dataclass (depending on configuration)
        """
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy.orm import sessionmaker

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

        # Create session factory
        session_factory = sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Execute INSERT and fetch the inserted record
        async with session_factory() as session:
            try:
                # Insert the record
                stmt = sa.insert(self._sa_table).values(**data)
                result = await session.execute(stmt)
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
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy.orm import sessionmaker

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

        # Create session factory
        session_factory = sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Execute UPDATE
        async with session_factory() as session:
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
                await session.rollback()
                raise
            except sa.exc.IntegrityError as e:
                await session.rollback()
                error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
                raise DeeBaseIntegrityError(
                    f"Failed to update table '{self._name}': {error_msg}",
                    table_name=self._name
                ) from e
            except Exception as e:
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
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy.orm import sessionmaker

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
        session_factory = sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        async with session_factory() as session:
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

                # Commit the session (even though we only did a SELECT)
                await session.commit()

            except Exception:
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
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy.orm import sessionmaker

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

        # Create session factory
        session_factory = sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Execute DELETE
        async with session_factory() as session:
            try:
                # Build DELETE statement with WHERE clause
                stmt = sa.delete(self._sa_table)
                for i, pk_col in enumerate(pk_cols):
                    stmt = stmt.where(pk_col == pk_values[i])

                # Apply xtra filters
                for col_name, value in self._xtra_filters.items():
                    stmt = stmt.where(self._sa_table.c[col_name] == value)

                result = await session.execute(stmt)
                await session.commit()

                # Check if any row was deleted
                if result.rowcount == 0:
                    raise NotFoundError(
                        f"Record with PK {pk_value} not found in table '{self._name}' or violates xtra filters",
                        table_name=self._name,
                        filters={**dict(zip([col.name for col in pk_cols], pk_values)), **self._xtra_filters}
                    )

            except (NotFoundError, ValidationError):
                await session.rollback()
                raise
            except Exception as e:
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
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy.orm import sessionmaker

        if not kwargs:
            raise ValidationError("lookup() requires at least one filter argument")

        # Create session factory
        session_factory = sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Execute SELECT with WHERE
        async with session_factory() as session:
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

                await session.commit()

                if row is None:
                    raise NotFoundError(
                        f"No record found in table '{self._name}' matching {kwargs}",
                        table_name=self._name,
                        filters={**kwargs, **self._xtra_filters}
                    )

                return self._to_record(row)

            except (NotFoundError, ValidationError, SchemaError):
                await session.rollback()
                raise
            except Exception as e:
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
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy.orm import sessionmaker

        # Create session factory
        session_factory = sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Execute SELECT
        async with session_factory() as session:
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
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy.orm import sessionmaker

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

        # Create session factory
        session_factory = sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Execute SELECT
        async with session_factory() as session:
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

                await session.commit()

                if row is None:
                    raise NotFoundError(
                        f"Record with PK {pk_value} not found in table '{self._name}'",
                        table_name=self._name,
                        filters=dict(zip([col.name for col in pk_cols], pk_values))
                    )

                return self._to_record(row)

            except (NotFoundError, ValidationError):
                await session.rollback()
                raise
            except Exception as e:
                await session.rollback()
                raise RuntimeError(
                    f"Unexpected error fetching from table '{self._name}': {str(e)}"
                ) from e

    async def drop(self) -> None:
        """Drop the table from the database."""
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy.orm import sessionmaker

        # Create session factory
        session_factory = sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Execute DROP TABLE
        async with session_factory() as session:
            try:
                await session.execute(sa.schema.DropTable(self._sa_table))
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def transform(self, **kwargs) -> None:
        """Transform the table structure.

        Args:
            **kwargs: Transformation parameters
        """
        # TODO: Implement in Phase 8
        raise NotImplementedError("transform() will be implemented in Phase 8")

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
