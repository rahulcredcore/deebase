"""View class for read-only database views."""

from .table import Table


class View(Table):
    """Represents a read-only database view.

    Views support query operations but not insert/update/delete.
    """

    async def insert(self, record):
        """Views are read-only."""
        raise NotImplementedError("Cannot insert into a view")

    async def update(self, record):
        """Views are read-only."""
        raise NotImplementedError("Cannot update a view")

    async def upsert(self, record):
        """Views are read-only."""
        raise NotImplementedError("Cannot upsert into a view")

    async def delete(self, pk_value):
        """Views are read-only."""
        raise NotImplementedError("Cannot delete from a view")

    async def drop(self):
        """Drop the view from the database."""
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy.orm import sessionmaker
        import sqlalchemy as sa

        # Create session factory
        session_factory = sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Execute DROP VIEW
        async with session_factory() as session:
            try:
                await session.execute(sa.text(f"DROP VIEW {self._name}"))
                await session.commit()
            except Exception:
                await session.rollback()
                raise
