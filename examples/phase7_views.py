"""
Phase 7 Example: Views Support

This example demonstrates Phase 7 view features:
- Creating views with db.create_view()
- Querying views (read-only operations)
- Dynamic view access via db.v.viewname
- View reflection with db.reflect_view()
- Views with dataclass support
- Dropping views
"""

import asyncio
from deebase import Database


async def main():
    print("=" * 70)
    print("Phase 7: Views Support")
    print("=" * 70)
    print()

    # Create in-memory database
    db = Database("sqlite+aiosqlite:///:memory:")

    # =========================================================================
    # 1. Create Tables and Data
    # =========================================================================
    print("1. Setting Up Tables and Data")
    print("-" * 70)

    class User:
        id: int
        name: str
        email: str
        active: bool

    class Post:
        id: int
        title: str
        user_id: int
        views: int
        published: bool

    users = await db.create(User, pk='id')
    posts = await db.create(Post, pk='id')

    # Insert users
    await users.insert({"name": "Alice", "email": "alice@example.com", "active": True})
    await users.insert({"name": "Bob", "email": "bob@example.com", "active": False})
    await users.insert({"name": "Charlie", "email": "charlie@example.com", "active": True})

    # Insert posts
    await posts.insert({"title": "First Post", "user_id": 1, "views": 100, "published": True})
    await posts.insert({"title": "Draft Post", "user_id": 1, "views": 0, "published": False})
    await posts.insert({"title": "Popular Post", "user_id": 3, "views": 1500, "published": True})
    await posts.insert({"title": "Another Post", "user_id": 3, "views": 50, "published": True})

    print(f"✓ Created tables: {users._name}, {posts._name}")
    print(f"✓ Inserted 3 users, 4 posts")
    print()

    # =========================================================================
    # 2. Create Views
    # =========================================================================
    print("\n2. Creating Views")
    print("-" * 70)

    # Simple view - active users only
    print("Creating 'active_users' view:")
    active_users = await db.create_view(
        "active_users",
        "SELECT * FROM user WHERE active = 1"
    )
    print(f"  ✓ Created: {active_users._name}")
    print()

    # View with aggregation
    print("Creating 'popular_posts' view:")
    popular_posts = await db.create_view(
        "popular_posts",
        "SELECT * FROM post WHERE views > 100 AND published = 1"
    )
    print(f"  ✓ Created: {popular_posts._name}")
    print()

    # View with JOIN
    print("Creating 'posts_with_authors' view:")
    posts_with_authors = await db.create_view(
        "posts_with_authors",
        """
        SELECT p.id, p.title, p.views, u.name as author_name, u.email as author_email
        FROM post p
        JOIN user u ON p.user_id = u.id
        WHERE p.published = 1
        """
    )
    print(f"  ✓ Created: {posts_with_authors._name}")
    print()

    # =========================================================================
    # 3. Query Views
    # =========================================================================
    print("\n3. Querying Views (Read-Only)")
    print("-" * 70)

    # SELECT from view
    print("SELECT from 'active_users':")
    active = await active_users()
    for user in active:
        print(f"  • {user['name']} ({user['email']})")
    print()

    # SELECT from view with limit
    print("SELECT from 'popular_posts' with limit:")
    popular = await popular_posts(limit=10)
    for post in popular:
        print(f"  • {post['title']}: {post['views']} views")
    print()

    # SELECT from JOIN view
    print("SELECT from 'posts_with_authors':")
    results = await posts_with_authors()
    for row in results:
        print(f"  • \"{row['title']}\" by {row['author_name']} ({row['views']} views)")
    print()

    # GET by pseudo-PK (first column)
    print("GET from view by first column (id):")
    post = await posts_with_authors[1]
    print(f"  • Got: {post}")
    print()

    # LOOKUP in view
    print("LOOKUP in view:")
    found = await popular_posts.lookup(title="Popular Post")
    print(f"  • Found: {found['title']} ({found['views']} views)")
    print()

    # =========================================================================
    # 4. Views Are Read-Only
    # =========================================================================
    print("\n4. Views Are Read-Only")
    print("-" * 70)

    # Try to insert - should fail
    print("Attempting INSERT on view:")
    try:
        await active_users.insert({"name": "Dave", "email": "dave@example.com", "active": True})
    except NotImplementedError as e:
        print(f"  ✗ Correctly blocked: {e}")
    print()

    # Try to update - should fail
    print("Attempting UPDATE on view:")
    try:
        await active_users.update({"id": 1, "name": "Alice Updated", "email": "alice@example.com", "active": True})
    except NotImplementedError as e:
        print(f"  ✗ Correctly blocked: {e}")
    print()

    # Try to delete - should fail
    print("Attempting DELETE on view:")
    try:
        await active_users.delete(1)
    except NotImplementedError as e:
        print(f"  ✗ Correctly blocked: {e}")
    print()

    # =========================================================================
    # 5. Dynamic View Access
    # =========================================================================
    print("\n5. Dynamic View Access via db.v")
    print("-" * 70)

    # Access by attribute
    print("Access via db.v.viewname:")
    view = db.v.active_users
    print(f"  • db.v.active_users → {view._name}")
    print()

    # Access by index
    print("Access via db.v['viewname']:")
    view = db.v['popular_posts']
    print(f"  • db.v['popular_posts'] → {view._name}")
    print()

    # Multiple views
    print("Access multiple views:")
    active, popular = db.v['active_users', 'popular_posts']
    print(f"  • db.v['active_users', 'popular_posts']")
    print(f"    → {active._name}, {popular._name}")
    print()

    # =========================================================================
    # 6. View Reflection
    # =========================================================================
    print("\n6. View Reflection")
    print("-" * 70)

    # Create view with raw SQL
    print("Creating view with raw SQL:")
    await db.q("""
        CREATE VIEW user_emails AS
        SELECT id, name, email FROM user
    """)
    print("  ✓ Created 'user_emails' with raw SQL")
    print()

    # Reflect the view
    print("Reflecting view:")
    user_emails = await db.reflect_view('user_emails')
    print(f"  ✓ Reflected: {user_emails._name}")
    print()

    # Now accessible via db.v
    print("Access via db.v:")
    view = db.v.user_emails
    print(f"  • db.v.user_emails → {view._name}")
    print()

    # Query it
    results = await view()
    print(f"Query results: {len(results)} rows")
    for row in results:
        print(f"  • {row['name']}: {row['email']}")
    print()

    # =========================================================================
    # 7. Views with Dataclass Support
    # =========================================================================
    print("\n7. Views with Dataclass Support")
    print("-" * 70)

    # Enable dataclass mode for view
    ActiveUserDC = active_users.dataclass()
    print(f"Generated dataclass: {ActiveUserDC}")
    print()

    # Query returns dataclass instances
    print("SELECT from view (dataclass mode):")
    active = await active_users()
    for user in active:
        print(f"  • {user.name} ({user.email}) - Type: {type(user).__name__}")
    print()

    # =========================================================================
    # 8. Drop Views
    # =========================================================================
    print("\n8. Dropping Views")
    print("-" * 70)

    print("Dropping 'user_emails' view:")
    await user_emails.drop()
    print("  ✓ Dropped")
    print()

    # Verify it's gone
    print("Verifying view is dropped:")
    try:
        _ = db.v.user_emails
    except AttributeError as e:
        print(f"  ✓ View not in cache: {str(e)[:50]}...")
    print()

    # Clean up
    await db.close()

    print("\n" + "=" * 70)
    print("Phase 7 Views Support - Complete!")
    print("=" * 70)
    print()
    print("Key Takeaways:")
    print("  • db.create_view(name, sql) creates database views")
    print("  • db.v.viewname provides sync cache access")
    print("  • Views support SELECT, GET, LOOKUP (read-only)")
    print("  • Views block INSERT, UPDATE, DELETE, UPSERT")
    print("  • db.reflect_view(name) loads existing views")
    print("  • Views work with dataclass mode")


if __name__ == "__main__":
    asyncio.run(main())
