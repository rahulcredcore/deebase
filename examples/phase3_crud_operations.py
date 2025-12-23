"""
Phase 3 Example: CRUD Operations

This example demonstrates all CRUD (Create, Read, Update, Delete) operations
implemented in Phase 3, including:
- Insert records with auto-generated PKs
- Select all/limited records
- Get records by primary key
- Lookup records by column values
- Update records
- Delete records
- Upsert (insert or update)
- Composite primary keys
- Rich types (Text, JSON, datetime)
"""

import asyncio
from datetime import datetime
from deebase import Database, Text, NotFoundError


async def main():
    print("=" * 70)
    print("Phase 3: CRUD Operations")
    print("=" * 70)
    print()

    # Create in-memory database
    db = Database("sqlite+aiosqlite:///:memory:")

    # =========================================================================
    # 1. Basic CRUD: Users Table
    # =========================================================================
    print("1. Basic CRUD Operations")
    print("-" * 70)

    class User:
        id: int
        name: str
        email: str
        age: int

    users = await db.create(User, pk='id')
    print(f"✓ Created table: {users._name}")
    print()

    # INSERT: Add records
    print("INSERT operations:")
    user1 = await users.insert({"name": "Alice", "email": "alice@example.com", "age": 30})
    print(f"  • Inserted: {user1}")

    user2 = await users.insert({"name": "Bob", "email": "bob@example.com", "age": 25})
    print(f"  • Inserted: {user2}")

    user3 = await users.insert({"name": "Charlie", "email": "charlie@example.com", "age": 35})
    print(f"  • Inserted: {user3}")
    print()

    # SELECT ALL: Get all records
    print("SELECT all records:")
    all_users = await users()
    for user in all_users:
        print(f"  • {user}")
    print()

    # SELECT with LIMIT
    print("SELECT with limit (2):")
    limited = await users(limit=2)
    for user in limited:
        print(f"  • {user}")
    print()

    # GET by PRIMARY KEY
    print(f"GET by primary key (id={user1['id']}):")
    fetched = await users[user1['id']]
    print(f"  • {fetched}")
    print()

    # LOOKUP by column value
    print("LOOKUP by email:")
    found = await users.lookup(email="bob@example.com")
    print(f"  • Found: {found}")
    print()

    # UPDATE
    print(f"UPDATE user {user1['id']}:")
    updated = await users.update({
        "id": user1['id'],
        "name": "Alice Smith",
        "email": "alice.smith@example.com",
        "age": 31
    })
    print(f"  • Updated: {updated}")
    print()

    # DELETE
    print(f"DELETE user {user3['id']}:")
    await users.delete(user3['id'])
    print(f"  • Deleted user with id={user3['id']}")

    remaining = await users()
    print(f"  • Remaining users: {len(remaining)}")
    print()

    # =========================================================================
    # 2. UPSERT: Insert or Update
    # =========================================================================
    print("\n2. UPSERT Operations")
    print("-" * 70)

    class Product:
        id: int
        name: str
        price: float
        stock: int

    products = await db.create(Product, pk='id')
    print(f"✓ Created table: {products._name}")
    print()

    # Upsert #1: Insert (no ID provided)
    print("UPSERT #1 (insert - no ID):")
    prod1 = await products.upsert({"name": "Widget", "price": 9.99, "stock": 100})
    print(f"  • Result: {prod1}")
    print()

    # Upsert #2: Update (ID exists)
    print(f"UPSERT #2 (update - ID {prod1['id']} exists):")
    prod1_updated = await products.upsert({
        "id": prod1['id'],
        "name": "Super Widget",
        "price": 14.99,
        "stock": 150
    })
    print(f"  • Result: {prod1_updated}")
    print()

    all_products = await products()
    print(f"Total products: {len(all_products)}")
    print()

    # =========================================================================
    # 3. Composite Primary Keys
    # =========================================================================
    print("\n3. Composite Primary Keys")
    print("-" * 70)

    class OrderItem:
        order_id: int
        item_id: int
        quantity: int
        price: float

    order_items = await db.create(OrderItem, pk=['order_id', 'item_id'])
    print(f"✓ Created table: {order_items._name}")
    print(f"  Primary keys: order_id, item_id")
    print()

    # Insert with composite PK
    print("INSERT with composite PK:")
    item1 = await order_items.insert({
        "order_id": 1,
        "item_id": 101,
        "quantity": 5,
        "price": 9.99
    })
    print(f"  • {item1}")

    item2 = await order_items.insert({
        "order_id": 1,
        "item_id": 102,
        "quantity": 3,
        "price": 14.99
    })
    print(f"  • {item2}")
    print()

    # Get by composite PK (using tuple)
    print("GET by composite PK (1, 101):")
    fetched_item = await order_items[(1, 101)]
    print(f"  • {fetched_item}")
    print()

    # Update with composite PK
    print("UPDATE with composite PK:")
    updated_item = await order_items.update({
        "order_id": 1,
        "item_id": 101,
        "quantity": 10,
        "price": 9.99
    })
    print(f"  • Updated: {updated_item}")
    print()

    # Delete by composite PK
    print("DELETE by composite PK (1, 102):")
    await order_items.delete((1, 102))
    remaining_items = await order_items()
    print(f"  • Remaining items: {len(remaining_items)}")
    print()

    # =========================================================================
    # 4. Rich Types: Text, JSON, datetime
    # =========================================================================
    print("\n4. Rich Types (Text, JSON, datetime)")
    print("-" * 70)

    class BlogPost:
        id: int
        title: str              # VARCHAR (short)
        slug: str               # VARCHAR (short)
        content: Text           # TEXT (unlimited)
        metadata: dict          # JSON
        created_at: datetime    # TIMESTAMP

    posts = await db.create(BlogPost, pk='id')
    print(f"✓ Created table: {posts._name}")
    print()

    # Insert with rich types
    print("INSERT with Text, JSON, datetime:")
    post = await posts.insert({
        "title": "Getting Started with DeeBase",
        "slug": "getting-started",
        "content": "A" * 5000,  # Very long text
        "metadata": {
            "author": "Alice",
            "tags": ["python", "database", "async"],
            "views": 0,
            "featured": True
        },
        "created_at": datetime.now()
    })
    print(f"  • Title: {post['title']}")
    print(f"  • Content length: {len(post['content'])} chars")
    print(f"  • Metadata: {post['metadata']}")
    print(f"  • Created: {post['created_at']}")
    print()

    # Update JSON field
    print("UPDATE JSON field:")
    post['metadata']['views'] = 100
    post['metadata']['tags'].append("tutorial")
    updated_post = await posts.update(post)
    print(f"  • New metadata: {updated_post['metadata']}")
    print()

    # =========================================================================
    # 5. with_pk Parameter
    # =========================================================================
    print("\n5. with_pk Parameter")
    print("-" * 70)

    # Select with_pk returns (pk_value, record) tuples
    print("SELECT with_pk=True:")
    results = await users(with_pk=True)
    for pk, record in results:
        print(f"  • PK={pk}: {record['name']} ({record['email']})")
    print()

    # For composite PKs, pk_value is a tuple
    print("SELECT with_pk=True (composite PK):")
    results = await order_items(with_pk=True)
    for pk, record in results:
        print(f"  • PK={pk}: quantity={record['quantity']}")
    print()

    # =========================================================================
    # 6. Error Handling
    # =========================================================================
    print("\n6. Error Handling")
    print("-" * 70)

    # NotFoundError on missing record
    print("GET non-existent record:")
    try:
        await users[9999]
    except NotFoundError as e:
        print(f"  • Caught NotFoundError: {e}")
    print()

    # NotFoundError on lookup
    print("LOOKUP non-existent record:")
    try:
        await users.lookup(email="nonexistent@example.com")
    except NotFoundError as e:
        print(f"  • Caught NotFoundError: {e}")
    print()

    # NotFoundError on update
    print("UPDATE non-existent record:")
    try:
        await users.update({"id": 9999, "name": "Ghost", "email": "ghost@example.com", "age": 0})
    except NotFoundError as e:
        print(f"  • Caught NotFoundError: {e}")
    print()

    # NotFoundError on delete
    print("DELETE non-existent record:")
    try:
        await users.delete(9999)
    except NotFoundError as e:
        print(f"  • Caught NotFoundError: {e}")
    print()

    # =========================================================================
    # 7. xtra() Filtering
    # =========================================================================
    print("\n7. xtra() Filtering")
    print("-" * 70)

    class Post:
        id: int
        title: str
        user_id: int

    all_posts = await db.create(Post, pk='id')
    print(f"✓ Created table: {all_posts._name}")
    print()

    # Insert posts for different users
    await all_posts.insert({"title": "Alice's First Post", "user_id": 1})
    await all_posts.insert({"title": "Alice's Second Post", "user_id": 1})
    await all_posts.insert({"title": "Bob's First Post", "user_id": 2})
    await all_posts.insert({"title": "Bob's Second Post", "user_id": 2})
    print("  • Inserted 4 posts (2 for user_id=1, 2 for user_id=2)")
    print()

    # Filter to user 1's posts
    user1_posts = all_posts.xtra(user_id=1)
    print("SELECT with xtra(user_id=1):")
    for post in await user1_posts():
        print(f"  • {post}")
    print()

    # Insert respects xtra filter
    print("INSERT with xtra(user_id=1) - auto-sets user_id:")
    new_post = await user1_posts.insert({"title": "Alice's Third Post"})
    print(f"  • {new_post}")
    print()

    # Clean up
    await db.close()

    print("\n" + "=" * 70)
    print("Phase 3 CRUD Operations - Complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
