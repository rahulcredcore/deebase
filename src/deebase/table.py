"""Table class for database table operations."""

from typing import Any, Optional
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine

from .column import ColumnAccessor
from .exceptions import NotFoundError
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
        if self._dataclass_cls is None:
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
        # TODO: Implement in Phase 3
        raise NotImplementedError("insert() will be implemented in Phase 3")

    async def update(self, record: dict | Any) -> dict | Any:
        """Update a record in the table.

        Args:
            record: Dict, dataclass, or object with primary key to update

        Returns:
            Updated record as dict or dataclass

        Raises:
            NotFoundError: If record not found or violates xtra filters
        """
        # TODO: Implement in Phase 3
        raise NotImplementedError("update() will be implemented in Phase 3")

    async def upsert(self, record: dict | Any) -> dict | Any:
        """Insert or update a record based on primary key existence.

        Args:
            record: Dict, dataclass, or object to upsert

        Returns:
            Upserted record as dict or dataclass
        """
        # TODO: Implement in Phase 7
        raise NotImplementedError("upsert() will be implemented in Phase 7")

    async def delete(self, pk_value: Any) -> None:
        """Delete a record by primary key.

        Args:
            pk_value: Primary key value (or tuple for composite keys)

        Raises:
            NotFoundError: If record not found or violates xtra filters
        """
        # TODO: Implement in Phase 3
        raise NotImplementedError("delete() will be implemented in Phase 3")

    async def lookup(self, **kwargs) -> dict | Any:
        """Find a single record matching the given criteria.

        Args:
            **kwargs: Column=value filters

        Returns:
            Single record as dict or dataclass

        Raises:
            NotFoundError: If no record matches
        """
        # TODO: Implement in Phase 3
        raise NotImplementedError("lookup() will be implemented in Phase 3")

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
        # TODO: Implement in Phase 3
        raise NotImplementedError("__call__() will be implemented in Phase 3")

    async def __getitem__(self, pk_value: Any) -> dict | Any:
        """Get a record by primary key.

        Args:
            pk_value: Primary key value (or tuple for composite keys)

        Returns:
            Record as dict or dataclass

        Raises:
            NotFoundError: If record not found
        """
        # TODO: Implement in Phase 3
        raise NotImplementedError("__getitem__() will be implemented in Phase 3")

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
        data = self._to_dict(row)
        if self._dataclass_cls:
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
