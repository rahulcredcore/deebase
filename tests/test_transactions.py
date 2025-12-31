"""Tests for transaction support."""

import pytest
from deebase import Database, NotFoundError, IntegrityError


class TestTransactionSetup:
    """Tests for transaction context manager setup and teardown."""

    @pytest.mark.asyncio
    async def test_transaction_context_manager(self, db):
        """Test that transaction context manager works."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        # Use transaction context manager
        async with db.transaction():
            await users.insert({"name": "Alice"})

        # Verify data was committed
        all_users = await users()
        assert len(all_users) == 1
        assert all_users[0]['name'] == "Alice"

    @pytest.mark.asyncio
    async def test_transaction_commit_on_success(self, db):
        """Test that transaction commits on successful completion."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        # Multiple operations in transaction
        async with db.transaction():
            await users.insert({"name": "Alice"})
            await users.insert({"name": "Bob"})
            await users.insert({"name": "Charlie"})

        # All inserts should be committed
        all_users = await users()
        assert len(all_users) == 3

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_exception(self, db):
        """Test that transaction rolls back on exception."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        # Transaction that raises exception
        try:
            async with db.transaction():
                await users.insert({"name": "Alice"})
                await users.insert({"name": "Bob"})
                raise RuntimeError("Simulated error")
        except RuntimeError:
            pass

        # No data should be committed
        all_users = await users()
        assert len(all_users) == 0

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_integrity_error(self, db):
        """Test that transaction rolls back on IntegrityError."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        # First insert succeeds
        await users.insert({"id": 1, "name": "Alice"})

        # Transaction with duplicate PK
        try:
            async with db.transaction():
                await users.insert({"name": "Bob"})
                await users.insert({"id": 1, "name": "Charlie"})  # Duplicate PK
        except IntegrityError:
            pass

        # Only Alice should exist (Bob rolled back)
        all_users = await users()
        assert len(all_users) == 1
        assert all_users[0]['name'] == "Alice"


class TestTransactionInsert:
    """Tests for insert operations within transactions."""

    @pytest.mark.asyncio
    async def test_multiple_inserts_in_transaction(self, db):
        """Test multiple inserts in a transaction."""
        class User:
            id: int
            name: str
            email: str

        users = await db.create(User, pk='id')

        async with db.transaction():
            user1 = await users.insert({"name": "Alice", "email": "alice@example.com"})
            user2 = await users.insert({"name": "Bob", "email": "bob@example.com"})
            user3 = await users.insert({"name": "Charlie", "email": "charlie@example.com"})

            # All inserts should return records with IDs
            assert user1['id'] is not None
            assert user2['id'] is not None
            assert user3['id'] is not None

        # Verify all committed
        all_users = await users()
        assert len(all_users) == 3

    @pytest.mark.asyncio
    async def test_insert_rollback_on_error(self, db):
        """Test that inserts roll back on error."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        try:
            async with db.transaction():
                await users.insert({"name": "Alice"})
                await users.insert({"name": "Bob"})
                # Trigger error by inserting invalid data
                await users.insert({"invalid_column": "value"})
        except Exception:
            pass

        # No users should exist
        all_users = await users()
        assert len(all_users) == 0

    @pytest.mark.asyncio
    async def test_insert_with_and_without_transaction(self, db):
        """Test mixing transactional and non-transactional inserts."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        # Non-transactional insert
        await users.insert({"name": "Alice"})

        # Transactional inserts
        async with db.transaction():
            await users.insert({"name": "Bob"})
            await users.insert({"name": "Charlie"})

        # Another non-transactional insert
        await users.insert({"name": "Dave"})

        all_users = await users()
        assert len(all_users) == 4


class TestTransactionUpdate:
    """Tests for update operations within transactions."""

    @pytest.mark.asyncio
    async def test_multiple_updates_in_transaction(self, db):
        """Test multiple updates in a transaction."""
        class User:
            id: int
            name: str
            email: str

        users = await db.create(User, pk='id')

        # Insert test data
        user1 = await users.insert({"name": "Alice", "email": "alice@old.com"})
        user2 = await users.insert({"name": "Bob", "email": "bob@old.com"})

        # Update in transaction
        async with db.transaction():
            user1['email'] = "alice@new.com"
            user2['email'] = "bob@new.com"
            await users.update(user1)
            await users.update(user2)

        # Verify updates
        updated1 = await users[user1['id']]
        updated2 = await users[user2['id']]
        assert updated1['email'] == "alice@new.com"
        assert updated2['email'] == "bob@new.com"

    @pytest.mark.asyncio
    async def test_update_rollback_on_error(self, db):
        """Test that updates roll back on error."""
        class User:
            id: int
            name: str
            email: str

        users = await db.create(User, pk='id')

        # Insert test data
        user1 = await users.insert({"name": "Alice", "email": "alice@old.com"})
        user2 = await users.insert({"name": "Bob", "email": "bob@old.com"})

        try:
            async with db.transaction():
                user1['email'] = "alice@new.com"
                await users.update(user1)
                user2['email'] = "bob@new.com"
                await users.update(user2)
                raise RuntimeError("Simulated error")
        except RuntimeError:
            pass

        # Updates should be rolled back
        unchanged1 = await users[user1['id']]
        unchanged2 = await users[user2['id']]
        assert unchanged1['email'] == "alice@old.com"
        assert unchanged2['email'] == "bob@old.com"


class TestTransactionUpsert:
    """Tests for upsert operations within transactions."""

    @pytest.mark.asyncio
    async def test_multiple_upserts_in_transaction(self, db):
        """Test multiple upserts in a transaction."""
        class User:
            id: int
            name: str
            email: str

        users = await db.create(User, pk='id')

        # Insert initial data
        await users.insert({"id": 1, "name": "Alice", "email": "alice@old.com"})

        # Upsert in transaction (one update, one insert)
        async with db.transaction():
            await users.upsert({"id": 1, "name": "Alice", "email": "alice@new.com"})  # Update
            await users.upsert({"id": 2, "name": "Bob", "email": "bob@example.com"})  # Insert

        # Verify both operations
        all_users = await users()
        assert len(all_users) == 2
        assert all_users[0]['email'] == "alice@new.com"
        assert all_users[1]['name'] == "Bob"

    @pytest.mark.asyncio
    async def test_upsert_rollback_on_error(self, db):
        """Test that upserts roll back on error."""
        class User:
            id: int
            name: str
            email: str

        users = await db.create(User, pk='id')

        # Insert initial data
        await users.insert({"id": 1, "name": "Alice", "email": "alice@old.com"})

        try:
            async with db.transaction():
                await users.upsert({"id": 1, "name": "Alice", "email": "alice@new.com"})
                await users.upsert({"id": 2, "name": "Bob", "email": "bob@example.com"})
                raise RuntimeError("Simulated error")
        except RuntimeError:
            pass

        # Upserts should be rolled back
        all_users = await users()
        assert len(all_users) == 1
        assert all_users[0]['email'] == "alice@old.com"


class TestTransactionDelete:
    """Tests for delete operations within transactions."""

    @pytest.mark.asyncio
    async def test_multiple_deletes_in_transaction(self, db):
        """Test multiple deletes in a transaction."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        # Insert test data
        user1 = await users.insert({"name": "Alice"})
        user2 = await users.insert({"name": "Bob"})
        user3 = await users.insert({"name": "Charlie"})

        # Delete in transaction
        async with db.transaction():
            await users.delete(user1['id'])
            await users.delete(user2['id'])

        # Only Charlie should remain
        all_users = await users()
        assert len(all_users) == 1
        assert all_users[0]['name'] == "Charlie"

    @pytest.mark.asyncio
    async def test_delete_rollback_on_error(self, db):
        """Test that deletes roll back on error."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        # Insert test data
        user1 = await users.insert({"name": "Alice"})
        user2 = await users.insert({"name": "Bob"})

        try:
            async with db.transaction():
                await users.delete(user1['id'])
                await users.delete(user2['id'])
                raise RuntimeError("Simulated error")
        except RuntimeError:
            pass

        # Deletes should be rolled back
        all_users = await users()
        assert len(all_users) == 2


class TestTransactionRead:
    """Tests for read operations within transactions."""

    @pytest.mark.asyncio
    async def test_select_all_in_transaction(self, db):
        """Test SELECT all within a transaction."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        await users.insert({"name": "Alice"})
        await users.insert({"name": "Bob"})

        async with db.transaction():
            all_users = await users()
            assert len(all_users) == 2

    @pytest.mark.asyncio
    async def test_get_by_pk_in_transaction(self, db):
        """Test GET by primary key within a transaction."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        user = await users.insert({"name": "Alice"})

        async with db.transaction():
            found = await users[user['id']]
            assert found['name'] == "Alice"

    @pytest.mark.asyncio
    async def test_lookup_in_transaction(self, db):
        """Test lookup within a transaction."""
        class User:
            id: int
            name: str
            email: str

        users = await db.create(User, pk='id')

        await users.insert({"name": "Alice", "email": "alice@example.com"})

        async with db.transaction():
            found = await users.lookup(email="alice@example.com")
            assert found['name'] == "Alice"

    @pytest.mark.asyncio
    async def test_consistent_reads_in_transaction(self, db):
        """Test that reads within a transaction see consistent data."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        user = await users.insert({"name": "Alice"})

        async with db.transaction():
            # Read
            found1 = await users[user['id']]
            assert found1['name'] == "Alice"

            # Update
            found1['name'] = "Alice Updated"
            updated = await users.update(found1)

            # Read again - should see updated value
            found2 = await users[user['id']]
            assert found2['name'] == "Alice Updated"

        # Verify committed
        final = await users[user['id']]
        assert final['name'] == "Alice Updated"


class TestTransactionMixed:
    """Tests for mixed operations within transactions."""

    @pytest.mark.asyncio
    async def test_mixed_crud_in_transaction(self, db):
        """Test mixed CRUD operations in a transaction."""
        class User:
            id: int
            name: str
            email: str

        users = await db.create(User, pk='id')

        # Initial data
        user1 = await users.insert({"name": "Alice", "email": "alice@old.com"})
        user2 = await users.insert({"name": "Bob", "email": "bob@example.com"})

        async with db.transaction():
            # Read
            alice = await users[user1['id']]
            assert alice['name'] == "Alice"

            # Update
            alice['email'] = "alice@new.com"
            await users.update(alice)

            # Insert
            user3 = await users.insert({"name": "Charlie", "email": "charlie@example.com"})

            # Delete
            await users.delete(user2['id'])

            # Read all
            all_users = await users()
            assert len(all_users) == 2  # Alice and Charlie

        # Verify final state
        final_users = await users()
        assert len(final_users) == 2
        assert final_users[0]['name'] == "Alice"
        assert final_users[0]['email'] == "alice@new.com"
        assert final_users[1]['name'] == "Charlie"

    @pytest.mark.asyncio
    async def test_transaction_with_xtra_filters(self, db):
        """Test transactions work with xtra filters."""
        class Post:
            id: int
            title: str
            author_id: int

        posts = await db.create(Post, pk='id')

        # Insert posts for different authors
        await posts.insert({"title": "Post 1", "author_id": 1})
        await posts.insert({"title": "Post 2", "author_id": 2})

        # Use xtra filter
        author1_posts = posts.xtra(author_id=1)

        async with db.transaction():
            # Insert with filter
            await author1_posts.insert({"title": "Post 3"})

            # Read with filter
            my_posts = await author1_posts()
            assert len(my_posts) == 2

        # Verify
        all_posts = await posts()
        assert len(all_posts) == 3
        author1_only = await author1_posts()
        assert len(author1_only) == 2


class TestTransactionEdgeCases:
    """Tests for edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_empty_transaction(self, db):
        """Test empty transaction (no operations)."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        # Empty transaction should work
        async with db.transaction():
            pass

        all_users = await users()
        assert len(all_users) == 0

    @pytest.mark.asyncio
    async def test_transaction_with_not_found_error(self, db):
        """Test transaction rollback on NotFoundError."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        await users.insert({"name": "Alice"})

        try:
            async with db.transaction():
                await users.insert({"name": "Bob"})
                await users[999]  # Not found
        except NotFoundError:
            pass

        # Bob's insert should be rolled back
        all_users = await users()
        assert len(all_users) == 1
        assert all_users[0]['name'] == "Alice"

    @pytest.mark.asyncio
    async def test_operations_outside_transaction_still_work(self, db):
        """Test that operations without transaction context still work."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        # Operations without transaction should auto-commit
        user1 = await users.insert({"name": "Alice"})
        user2 = await users.insert({"name": "Bob"})

        all_users = await users()
        assert len(all_users) == 2

        # Update without transaction
        user1['name'] = "Alice Updated"
        await users.update(user1)

        # Delete without transaction
        await users.delete(user2['id'])

        final_users = await users()
        assert len(final_users) == 1
        assert final_users[0]['name'] == "Alice Updated"
