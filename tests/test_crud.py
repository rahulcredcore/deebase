"""Tests for CRUD operations (Phase 3)."""

import pytest
from typing import Optional
from datetime import datetime
from deebase import Database, Text, NotFoundError


class TestBasicCRUD:
    """Tests for basic CRUD operations with dicts."""

    @pytest.mark.asyncio
    async def test_insert_and_select_all(self, db):
        """Test inserting records and selecting all."""
        class User:
            id: int
            name: str
            email: str

        users = await db.create(User, pk='id')

        # Insert records
        user1 = await users.insert({"name": "Alice", "email": "alice@example.com"})
        user2 = await users.insert({"name": "Bob", "email": "bob@example.com"})

        # Verify inserted records have IDs
        assert user1['id'] is not None
        assert user1['name'] == "Alice"
        assert user1['email'] == "alice@example.com"

        assert user2['id'] is not None
        assert user2['name'] == "Bob"

        # Select all records
        all_users = await users()
        assert len(all_users) == 2
        assert all_users[0]['name'] == "Alice"
        assert all_users[1]['name'] == "Bob"

    @pytest.mark.asyncio
    async def test_select_with_limit(self, db):
        """Test selecting records with a limit."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        # Insert multiple records
        await users.insert({"name": "Alice"})
        await users.insert({"name": "Bob"})
        await users.insert({"name": "Charlie"})

        # Select with limit
        limited = await users(limit=2)
        assert len(limited) == 2

    @pytest.mark.asyncio
    async def test_get_by_pk(self, db):
        """Test getting a record by primary key."""
        class User:
            id: int
            name: str
            email: str

        users = await db.create(User, pk='id')

        # Insert a record
        inserted = await users.insert({"name": "Alice", "email": "alice@example.com"})
        user_id = inserted['id']

        # Get by PK
        user = await users[user_id]
        assert user['id'] == user_id
        assert user['name'] == "Alice"
        assert user['email'] == "alice@example.com"

    @pytest.mark.asyncio
    async def test_get_by_pk_not_found(self, db):
        """Test that getting by non-existent PK raises NotFoundError."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        # Try to get non-existent record
        with pytest.raises(NotFoundError):
            await users[999]

    @pytest.mark.asyncio
    async def test_lookup(self, db):
        """Test looking up a record by column values."""
        class User:
            id: int
            name: str
            email: str

        users = await db.create(User, pk='id')

        # Insert records
        await users.insert({"name": "Alice", "email": "alice@example.com"})
        await users.insert({"name": "Bob", "email": "bob@example.com"})

        # Lookup by email
        user = await users.lookup(email="alice@example.com")
        assert user['name'] == "Alice"
        assert user['email'] == "alice@example.com"

        # Lookup by name
        user = await users.lookup(name="Bob")
        assert user['email'] == "bob@example.com"

    @pytest.mark.asyncio
    async def test_lookup_not_found(self, db):
        """Test that lookup raises NotFoundError when no match."""
        class User:
            id: int
            name: str
            email: str

        users = await db.create(User, pk='id')

        await users.insert({"name": "Alice", "email": "alice@example.com"})

        # Lookup non-existent record
        with pytest.raises(NotFoundError):
            await users.lookup(email="nonexistent@example.com")

    @pytest.mark.asyncio
    async def test_update(self, db):
        """Test updating a record."""
        class User:
            id: int
            name: str
            email: str

        users = await db.create(User, pk='id')

        # Insert a record
        user = await users.insert({"name": "Alice", "email": "alice@example.com"})
        user_id = user['id']

        # Update the record
        updated = await users.update({
            "id": user_id,
            "name": "Alice Updated",
            "email": "alice.new@example.com"
        })

        assert updated['id'] == user_id
        assert updated['name'] == "Alice Updated"
        assert updated['email'] == "alice.new@example.com"

        # Verify the update persisted
        fetched = await users[user_id]
        assert fetched['name'] == "Alice Updated"
        assert fetched['email'] == "alice.new@example.com"

    @pytest.mark.asyncio
    async def test_update_not_found(self, db):
        """Test that updating non-existent record raises NotFoundError."""
        class User:
            id: int
            name: str
            email: str

        users = await db.create(User, pk='id')

        # Try to update non-existent record
        with pytest.raises(NotFoundError):
            await users.update({"id": 999, "name": "Ghost", "email": "ghost@example.com"})

    @pytest.mark.asyncio
    async def test_delete(self, db):
        """Test deleting a record."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        # Insert a record
        user = await users.insert({"name": "Alice"})
        user_id = user['id']

        # Verify it exists
        assert await users[user_id] is not None

        # Delete it
        await users.delete(user_id)

        # Verify it's gone
        with pytest.raises(NotFoundError):
            await users[user_id]

    @pytest.mark.asyncio
    async def test_delete_not_found(self, db):
        """Test that deleting non-existent record raises NotFoundError."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        # Try to delete non-existent record
        with pytest.raises(NotFoundError):
            await users.delete(999)

    @pytest.mark.asyncio
    async def test_upsert_insert_case(self, db):
        """Test upsert when record doesn't exist (insert behavior)."""
        class User:
            id: int
            name: str
            email: str

        users = await db.create(User, pk='id')

        # Upsert a new record (should insert)
        user = await users.upsert({"name": "Alice", "email": "alice@example.com"})

        assert user['id'] is not None
        assert user['name'] == "Alice"

        # Verify it was inserted
        all_users = await users()
        assert len(all_users) == 1

    @pytest.mark.asyncio
    async def test_upsert_update_case(self, db):
        """Test upsert when record exists (update behavior)."""
        class User:
            id: int
            name: str
            email: str

        users = await db.create(User, pk='id')

        # Insert a record first
        user = await users.insert({"name": "Alice", "email": "alice@example.com"})
        user_id = user['id']

        # Upsert with same ID (should update)
        updated = await users.upsert({
            "id": user_id,
            "name": "Alice Updated",
            "email": "alice.new@example.com"
        })

        assert updated['id'] == user_id
        assert updated['name'] == "Alice Updated"
        assert updated['email'] == "alice.new@example.com"

        # Verify only one record exists
        all_users = await users()
        assert len(all_users) == 1

    @pytest.mark.asyncio
    async def test_full_crud_cycle(self, db):
        """Test a complete CRUD cycle: create, read, update, delete."""
        class Product:
            id: int
            name: str
            price: float

        products = await db.create(Product, pk='id')

        # Create
        product = await products.insert({"name": "Widget", "price": 9.99})
        product_id = product['id']

        # Read
        fetched = await products[product_id]
        assert fetched['name'] == "Widget"
        assert fetched['price'] == 9.99

        # Update
        await products.update({"id": product_id, "name": "Super Widget", "price": 19.99})
        updated = await products[product_id]
        assert updated['name'] == "Super Widget"
        assert updated['price'] == 19.99

        # Delete
        await products.delete(product_id)
        with pytest.raises(NotFoundError):
            await products[product_id]


class TestCompositeKeys:
    """Tests for tables with composite primary keys."""

    @pytest.mark.asyncio
    async def test_insert_with_composite_pk(self, db):
        """Test inserting records with composite primary key."""
        class OrderItem:
            order_id: int
            item_id: int
            quantity: int

        order_items = await db.create(OrderItem, pk=['order_id', 'item_id'])

        # Insert a record
        item = await order_items.insert({
            "order_id": 1,
            "item_id": 101,
            "quantity": 5
        })

        assert item['order_id'] == 1
        assert item['item_id'] == 101
        assert item['quantity'] == 5

    @pytest.mark.asyncio
    async def test_get_by_composite_pk(self, db):
        """Test getting a record by composite primary key."""
        class OrderItem:
            order_id: int
            item_id: int
            quantity: int

        order_items = await db.create(OrderItem, pk=['order_id', 'item_id'])

        # Insert a record
        await order_items.insert({"order_id": 1, "item_id": 101, "quantity": 5})

        # Get by composite PK (using tuple)
        item = await order_items[(1, 101)]
        assert item['order_id'] == 1
        assert item['item_id'] == 101
        assert item['quantity'] == 5

    @pytest.mark.asyncio
    async def test_update_with_composite_pk(self, db):
        """Test updating a record with composite primary key."""
        class OrderItem:
            order_id: int
            item_id: int
            quantity: int

        order_items = await db.create(OrderItem, pk=['order_id', 'item_id'])

        # Insert a record
        await order_items.insert({"order_id": 1, "item_id": 101, "quantity": 5})

        # Update it
        updated = await order_items.update({
            "order_id": 1,
            "item_id": 101,
            "quantity": 10
        })

        assert updated['quantity'] == 10

    @pytest.mark.asyncio
    async def test_delete_with_composite_pk(self, db):
        """Test deleting a record with composite primary key."""
        class OrderItem:
            order_id: int
            item_id: int
            quantity: int

        order_items = await db.create(OrderItem, pk=['order_id', 'item_id'])

        # Insert a record
        await order_items.insert({"order_id": 1, "item_id": 101, "quantity": 5})

        # Delete by composite PK (using tuple)
        await order_items.delete((1, 101))

        # Verify it's gone
        with pytest.raises(NotFoundError):
            await order_items[(1, 101)]


class TestWithPK:
    """Tests for with_pk parameter in __call__."""

    @pytest.mark.asyncio
    async def test_select_with_pk_single(self, db):
        """Test selecting records with_pk=True for single PK."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        # Insert records
        user1 = await users.insert({"name": "Alice"})
        user2 = await users.insert({"name": "Bob"})

        # Select with PK
        results = await users(with_pk=True)

        assert len(results) == 2

        # Results should be tuples of (pk_value, record)
        pk1, record1 = results[0]
        pk2, record2 = results[1]

        assert pk1 == user1['id']
        assert record1['name'] == "Alice"

        assert pk2 == user2['id']
        assert record2['name'] == "Bob"

    @pytest.mark.asyncio
    async def test_select_with_pk_composite(self, db):
        """Test selecting records with_pk=True for composite PK."""
        class OrderItem:
            order_id: int
            item_id: int
            quantity: int

        order_items = await db.create(OrderItem, pk=['order_id', 'item_id'])

        # Insert records
        await order_items.insert({"order_id": 1, "item_id": 101, "quantity": 5})
        await order_items.insert({"order_id": 1, "item_id": 102, "quantity": 3})

        # Select with PK
        results = await order_items(with_pk=True)

        assert len(results) == 2

        # For composite PKs, pk_value should be a tuple
        pk1, record1 = results[0]
        assert pk1 == (1, 101)
        assert record1['quantity'] == 5

        pk2, record2 = results[1]
        assert pk2 == (1, 102)
        assert record2['quantity'] == 3


class TestRichTypes:
    """Tests for CRUD operations with rich types (Text, JSON, datetime)."""

    @pytest.mark.asyncio
    async def test_crud_with_text_type(self, db):
        """Test CRUD operations with Text type."""
        class Article:
            id: int
            title: str
            content: Text

        articles = await db.create(Article, pk='id')

        # Insert with long text
        long_content = "A" * 10000  # Very long text
        article = await articles.insert({
            "title": "Long Article",
            "content": long_content
        })

        assert article['content'] == long_content

        # Fetch and verify
        fetched = await articles[article['id']]
        assert fetched['content'] == long_content

    @pytest.mark.asyncio
    async def test_crud_with_json_type(self, db):
        """Test CRUD operations with JSON (dict) type."""
        class Post:
            id: int
            title: str
            metadata: dict

        posts = await db.create(Post, pk='id')

        # Insert with JSON data
        post = await posts.insert({
            "title": "My Post",
            "metadata": {"author": "Alice", "tags": ["python", "database"], "views": 100}
        })

        assert post['metadata']['author'] == "Alice"
        assert post['metadata']['tags'] == ["python", "database"]

        # Update JSON field
        updated = await posts.update({
            "id": post['id'],
            "title": "My Post",
            "metadata": {"author": "Alice", "tags": ["python"], "views": 150}
        })

        assert updated['metadata']['views'] == 150
        assert len(updated['metadata']['tags']) == 1

    @pytest.mark.asyncio
    async def test_crud_with_datetime(self, db):
        """Test CRUD operations with datetime type."""
        class Event:
            id: int
            name: str
            created_at: datetime

        events = await db.create(Event, pk='id')

        # Insert with datetime
        now = datetime.now()
        event = await events.insert({
            "name": "Conference",
            "created_at": now
        })

        # Verify datetime was stored and retrieved
        assert event['created_at'] is not None
        # Note: Some precision may be lost in SQLite, so compare with tolerance
        assert abs((event['created_at'] - now).total_seconds()) < 1

    @pytest.mark.asyncio
    async def test_crud_with_optional_fields(self, db):
        """Test CRUD operations with Optional fields."""
        class User:
            id: int
            name: str
            email: Optional[str]
            bio: Optional[Text]

        users = await db.create(User, pk='id')

        # Insert with some None values
        user = await users.insert({
            "name": "Alice",
            "email": "alice@example.com",
            "bio": None
        })

        assert user['name'] == "Alice"
        assert user['email'] == "alice@example.com"
        assert user['bio'] is None

        # Update to set bio
        updated = await users.update({
            "id": user['id'],
            "name": "Alice",
            "email": "alice@example.com",
            "bio": "Software engineer"
        })

        assert updated['bio'] == "Software engineer"


class TestXtraFilters:
    """Tests for xtra() filtering on CRUD operations."""

    @pytest.mark.asyncio
    async def test_insert_with_xtra(self, db):
        """Test that insert respects xtra filters."""
        class Post:
            id: int
            title: str
            user_id: int

        posts = await db.create(Post, pk='id')

        # Create xtra-filtered table
        user1_posts = posts.xtra(user_id=1)

        # Insert should auto-set user_id
        post = await user1_posts.insert({"title": "My Post"})
        assert post['user_id'] == 1

        # All posts for user 1
        all_posts = await user1_posts()
        assert len(all_posts) == 1

    @pytest.mark.asyncio
    async def test_select_with_xtra(self, db):
        """Test that select respects xtra filters."""
        class Post:
            id: int
            title: str
            user_id: int

        posts = await db.create(Post, pk='id')

        # Insert posts for different users
        await posts.insert({"title": "User 1 Post", "user_id": 1})
        await posts.insert({"title": "User 2 Post", "user_id": 2})
        await posts.insert({"title": "Another User 1 Post", "user_id": 1})

        # Filter to user 1
        user1_posts = posts.xtra(user_id=1)
        filtered = await user1_posts()

        assert len(filtered) == 2
        assert all(p['user_id'] == 1 for p in filtered)

    @pytest.mark.asyncio
    async def test_lookup_with_xtra(self, db):
        """Test that lookup respects xtra filters."""
        class Post:
            id: int
            title: str
            user_id: int

        posts = await db.create(Post, pk='id')

        await posts.insert({"title": "Post 1", "user_id": 1})
        await posts.insert({"title": "Post 2", "user_id": 2})

        # Filter to user 1 and lookup
        user1_posts = posts.xtra(user_id=1)
        post = await user1_posts.lookup(title="Post 1")
        assert post['title'] == "Post 1"

        # Lookup should fail for user 2's post
        with pytest.raises(NotFoundError):
            await user1_posts.lookup(title="Post 2")

    @pytest.mark.asyncio
    async def test_delete_with_xtra(self, db):
        """Test that delete respects xtra filters."""
        class Post:
            id: int
            title: str
            user_id: int

        posts = await db.create(Post, pk='id')

        post1 = await posts.insert({"title": "User 1 Post", "user_id": 1})
        post2 = await posts.insert({"title": "User 2 Post", "user_id": 2})

        # Try to delete user 2's post through user 1 filter
        user1_posts = posts.xtra(user_id=1)

        with pytest.raises(NotFoundError):
            await user1_posts.delete(post2['id'])

        # Can delete user 1's post
        await user1_posts.delete(post1['id'])

        # Verify user 2's post still exists
        all_posts = await posts()
        assert len(all_posts) == 1
        assert all_posts[0]['user_id'] == 2
