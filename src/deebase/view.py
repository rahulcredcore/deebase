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
        # TODO: Implement in Phase 7
        raise NotImplementedError("drop() will be implemented in Phase 7")
