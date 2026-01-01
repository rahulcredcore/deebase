"""
Complete Example: Building a Blog Database

This example showcases ALL DeeBase capabilities from Phases 1-11:
- Phase 1: Raw SQL queries
- Phase 2: Table creation from Python classes
- Phase 3: CRUD operations with rich types
- Phase 4: Dataclass support for type safety
- Phase 5: Reflection and dynamic table access
- Phase 6: xtra() filtering for scoped queries
- Phase 7: Database views for read-only access
- Phase 8: Exception handling with rich context
- Phase 9: Transactions for atomic operations
- Phase 10: Foreign keys and default values
- Phase 11: FK relationship navigation
"""

import asyncio
from typing import Optional
from datetime import datetime
from dataclasses import dataclass
from deebase import (
    Database, Text, ForeignKey,
    NotFoundError, IntegrityError, ValidationError
)


async def main():
    print("=" * 70)
    print("Complete Example: Full-Featured Blog Database")
    print("Showcasing ALL DeeBase capabilities (Phases 1-11)")
    print("=" * 70)
    print()

    # Initialize database
    db = Database("sqlite+aiosqlite:///:memory:")

    # =========================================================================
    # Phase 10: Foreign Keys & Defaults
    # =========================================================================
    print("1. Defining schema with Foreign Keys & Defaults (Phase 10)")
    print("-" * 70)

    # Author table with default status
    class Author:
        id: int
        name: str
        email: str
        bio: Optional[Text]
        status: str = "active"  # SQL DEFAULT 'active'

    # Category table
    class Category:
        id: int
        name: str
        slug: str

    # Post table with FK relationships and defaults
    class Post:
        id: int
        title: str
        slug: str
        content: Text
        excerpt: Optional[str]
        author_id: ForeignKey[int, "author"]      # FK to author.id
        category_id: ForeignKey[int, "category"]  # FK to category.id
        metadata: dict
        published: bool = False  # SQL DEFAULT 0
        view_count: int = 0      # SQL DEFAULT 0
        created_at: datetime
        updated_at: Optional[datetime]

    # Comment table with FK to post
    class Comment:
        id: int
        post_id: ForeignKey[int, "post"]  # FK to post.id
        author_name: str
        content: Text
        approved: bool = False  # SQL DEFAULT 0
        created_at: datetime

    print("   Defined: Author (with status default)")
    print("   Defined: Category")
    print("   Defined: Post (with FK to author, category + defaults)")
    print("   Defined: Comment (with FK to post + default)")
    print()

    # =========================================================================
    # Phase 2: Table Creation
    # =========================================================================
    print("2. Creating tables with if_not_exists (Phase 2 + 10)")
    print("-" * 70)

    # Create tables with if_not_exists for safety
    authors = await db.create(Author, pk='id', if_not_exists=True)
    categories = await db.create(Category, pk='id', if_not_exists=True)
    posts = await db.create(Post, pk='id', if_not_exists=True)
    comments = await db.create(Comment, pk='id', if_not_exists=True)

    # Enable FK enforcement in SQLite
    await db.q("PRAGMA foreign_keys = ON")

    print(f"   Created: {authors._name} (with status default)")
    print(f"   Created: {categories._name}")
    print(f"   Created: {posts._name} (with FK constraints + defaults)")
    print(f"   Created: {comments._name} (with FK constraint + default)")
    print("   Enabled: Foreign key enforcement")
    print()

    # =========================================================================
    # Phase 3: CRUD Operations
    # =========================================================================
    print("3. Inserting data with CRUD operations (Phase 3)")
    print("-" * 70)

    # Insert categories
    cat1 = await categories.insert({"name": "Technology", "slug": "tech"})
    cat2 = await categories.insert({"name": "Tutorial", "slug": "tutorial"})
    print(f"   Inserted categories: {cat1['name']}, {cat2['name']}")

    # Insert authors (status will default to "active")
    author1 = await authors.insert({
        "name": "Alice Smith",
        "email": "alice@example.com",
        "bio": "Tech writer and Python enthusiast"
    })
    author2 = await authors.insert({
        "name": "Bob Jones",
        "email": "bob@example.com",
        "bio": "Software engineer and blogger"
    })
    print(f"   Inserted authors: {author1['name']} (status={author1['status']})")
    print(f"                     {author2['name']} (status={author2['status']})")

    # Insert posts (view_count and published will use defaults)
    post1 = await posts.insert({
        "title": "Getting Started with DeeBase",
        "slug": "getting-started-deebase",
        "content": "This is a comprehensive guide to DeeBase, an async database library...",
        "excerpt": "Learn async database operations with DeeBase",
        "author_id": author1['id'],
        "category_id": cat2['id'],
        "metadata": {"tags": ["python", "async", "database"], "featured": True},
        "created_at": datetime(2025, 12, 20, 10, 0, 0)
    })
    print(f"   Inserted post: '{post1['title']}'")
    print(f"      view_count={post1['view_count']} (default), published={post1['published']} (default)")

    # Insert another post with explicit values
    post2 = await posts.insert({
        "title": "Advanced SQLAlchemy Patterns",
        "slug": "advanced-sqlalchemy",
        "content": "Explore advanced patterns for using SQLAlchemy with async Python...",
        "author_id": author2['id'],
        "category_id": cat1['id'],
        "metadata": {"tags": ["sqlalchemy", "patterns"], "featured": False},
        "published": True,
        "view_count": 156,
        "created_at": datetime(2025, 12, 18, 14, 30, 0)
    })
    print(f"   Inserted post: '{post2['title']}'")
    print(f"      view_count={post2['view_count']} (explicit), published={post2['published']} (explicit)")

    # Insert comments (approved will default to False)
    comment1 = await comments.insert({
        "post_id": post1['id'],
        "author_name": "Reader1",
        "content": "Great introduction!",
        "created_at": datetime.now()
    })
    print(f"   Inserted comment: approved={comment1['approved']} (default)")
    print()

    # =========================================================================
    # Phase 8: Exception Handling
    # =========================================================================
    print("4. Exception handling (Phase 8)")
    print("-" * 70)

    # FK constraint violation
    try:
        await posts.insert({
            "title": "Invalid Post",
            "slug": "invalid",
            "content": "This will fail",
            "author_id": 999,  # Non-existent author!
            "category_id": 1,
            "metadata": {},
            "created_at": datetime.now()
        })
    except IntegrityError as e:
        print(f"   IntegrityError caught: FK constraint violated")
        print(f"      Table: {e.table_name}")

    # NotFoundError
    try:
        await posts[999]
    except NotFoundError as e:
        print(f"   NotFoundError caught: {e.message}")

    # ValidationError
    try:
        await posts.update({"title": "Missing PK"})
    except ValidationError as e:
        print(f"   ValidationError caught: {e.message}")
    print()

    # =========================================================================
    # Phase 9: Transactions
    # =========================================================================
    print("5. Atomic transactions (Phase 9)")
    print("-" * 70)

    # Successful transaction
    async with db.transaction():
        # Publish post1 and increment view count atomically
        post1['published'] = True
        post1['view_count'] = 50
        await posts.update(post1)
        # Add another comment
        await comments.insert({
            "post_id": post1['id'],
            "author_name": "Reader2",
            "content": "Thanks for sharing!",
            "created_at": datetime.now()
        })
    print("   Transaction 1: Published post + added comment (committed)")

    # Transaction with rollback
    try:
        async with db.transaction():
            await posts.insert({
                "title": "Will be rolled back",
                "slug": "rollback-test",
                "content": "This won't persist",
                "author_id": 1,
                "category_id": 1,
                "metadata": {},
                "created_at": datetime.now()
            })
            raise ValueError("Simulated error!")
    except ValueError:
        pass

    # Verify rollback
    all_posts = await posts()
    print(f"   Transaction 2: Rolled back (total posts still = {len(all_posts)})")
    print()

    # =========================================================================
    # Phase 6: xtra() Filtering
    # =========================================================================
    print("6. Scoped queries with xtra() (Phase 6)")
    print("-" * 70)

    # Create filtered view of author's posts
    alice_posts = posts.xtra(author_id=author1['id'])
    bob_posts = posts.xtra(author_id=author2['id'])

    alice_count = len(await alice_posts())
    bob_count = len(await bob_posts())
    print(f"   Alice's posts: {alice_count}")
    print(f"   Bob's posts: {bob_count}")

    # Chain filters
    published_posts = posts.xtra(published=True)
    published_count = len(await published_posts())
    print(f"   Published posts: {published_count}")
    print()

    # =========================================================================
    # Phase 11: FK Navigation
    # =========================================================================
    print("7. FK Navigation (Phase 11)")
    print("-" * 70)

    # Check FK metadata
    print(f"   Post.foreign_keys:")
    for fk in posts.foreign_keys:
        print(f"      {fk['column']} -> {fk['references']}")

    # Convenience API: Navigate from post to author
    post_record = await posts[1]
    author_via_fk = await posts.fk.author_id(post_record)
    print(f"\n   Convenience API: posts.fk.author_id(post)")
    print(f"      Post: '{post_record['title']}'")
    print(f"      Author: {author_via_fk['name']}")

    # Power user API: Navigate using get_parent
    category_via_parent = await posts.get_parent(post_record, "category_id")
    print(f"\n   Power user API: posts.get_parent(post, 'category_id')")
    print(f"      Category: {category_via_parent['name']}")

    # Reverse navigation: Get all posts by an author
    alice_record = await authors.lookup(name="Alice Smith")
    alice_posts = await authors.get_children(alice_record, "post", "author_id")
    print(f"\n   Reverse navigation: authors.get_children(alice, 'post', 'author_id')")
    print(f"      Alice's posts: {len(alice_posts)}")

    # Get comments on a post
    post_comments = await posts.get_children(post_record, comments, "post_id")
    print(f"\n   Reverse navigation: posts.get_children(post, comments, 'post_id')")
    print(f"      Comments on '{post_record['title']}': {len(post_comments)}")
    print()

    # =========================================================================
    # Phase 4: Dataclass Support
    # =========================================================================
    print("8. Dataclass support for type safety (Phase 4)")
    print("-" * 70)

    # Generate dataclass from table
    PostDC = posts.dataclass()
    print(f"   Generated dataclass: {PostDC.__name__}")

    # All operations now return dataclass instances
    all_posts_dc = await posts()
    for p in all_posts_dc:
        print(f"   - {p.title}: {p.view_count} views (type: {type(p).__name__})")
    print()

    # =========================================================================
    # Phase 7: Views - Including Views for Joins Pattern
    # =========================================================================
    print("9. Database views for joins (Phase 7)")
    print("-" * 70)

    # Views are the elegant solution for JOINs in DeeBase!
    # Instead of an N+1 pattern (fetching each FK separately),
    # create a view with JOIN and use it like a table.

    # Create view for published posts with author info
    published_view = await db.create_view(
        "published_posts",
        """
        SELECT p.id, p.title, p.view_count, a.name as author_name, c.name as category
        FROM post p
        JOIN author a ON p.author_id = a.id
        JOIN category c ON p.category_id = c.id
        WHERE p.published = 1
        """
    )
    print(f"   Created view: {published_view._name}")
    print("   (Uses JOIN to get post + author + category in one query)")

    # Query view - full DeeBase API works!
    results = await published_view()
    print(f"\n   Published posts view ({len(results)} rows):")
    for row in results:
        print(f"      '{row['title']}' by {row['author_name']} [{row['category']}]")

    # Generate dataclass from view for type-safe access
    PublishedPostDC = published_view.dataclass()
    print(f"\n   Generated dataclass from view: {PublishedPostDC.__name__}")
    typed_results = await published_view()
    for p in typed_results:
        print(f"      Type-safe access: {p.title} by {p.author_name}")

    # Access via db.v
    view = db.v.published_posts
    print(f"\n   Accessed via db.v: {view._name}")

    # Create another view for aggregations
    await db.create_view(
        "author_stats",
        """
        SELECT
            a.id, a.name,
            COUNT(p.id) as post_count,
            COALESCE(SUM(p.view_count), 0) as total_views
        FROM author a
        LEFT JOIN post p ON a.id = p.author_id
        GROUP BY a.id, a.name
        """
    )
    stats = await db.v.author_stats()
    print(f"\n   Author stats view (aggregation):")
    for s in stats:
        print(f"      {s['name']}: {s['post_count']} posts, {s['total_views']} views")
    print()

    # =========================================================================
    # Phase 5: Reflection & Dynamic Access
    # =========================================================================
    print("10. Reflection and dynamic access (Phase 5)")
    print("-" * 70)

    # Create a table with raw SQL
    await db.q("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY,
            action TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    await db.q("INSERT INTO audit_log (action, timestamp) VALUES ('startup', datetime('now'))")

    # Reflect the table
    await db.reflect_table('audit_log')

    # Access via db.t
    audit = db.t.audit_log
    logs = await audit()
    print(f"   Reflected audit_log table: {len(logs)} entries")

    # Access all tables via db.t
    print(f"   Dynamic access: db.t.author → {db.t.author._name}")
    print(f"   Dynamic access: db.t.post → {db.t.post._name}")

    # Multiple table access
    a, p, c = db.t['author', 'post', 'comment']
    print(f"   Multiple access: {a._name}, {p._name}, {c._name}")
    print()

    # =========================================================================
    # Phase 1: Raw SQL (with JOIN)
    # =========================================================================
    print("11. Complex queries with raw SQL (Phase 1)")
    print("-" * 70)

    results = await db.q("""
        SELECT
            p.title,
            p.view_count,
            a.name as author,
            c.name as category,
            (SELECT COUNT(*) FROM comment WHERE post_id = p.id) as comment_count
        FROM post p
        JOIN author a ON p.author_id = a.id
        JOIN category c ON p.category_id = c.id
        ORDER BY p.view_count DESC
    """)

    print("   Blog posts with stats:")
    for r in results:
        print(f"      '{r['title']}'")
        print(f"         Author: {r['author']}, Category: {r['category']}")
        print(f"         Views: {r['view_count']}, Comments: {r['comment_count']}")
    print()

    # =========================================================================
    # Schema Inspection
    # =========================================================================
    print("12. Schema inspection")
    print("-" * 70)
    print("\nPost table schema (showing FK constraints and defaults):")
    print(posts.schema)
    print()

    # =========================================================================
    # Cleanup
    # =========================================================================
    print("13. Cleanup")
    print("-" * 70)
    await published_view.drop()
    await db.v.author_stats.drop()
    await comments.drop()
    await posts.drop()
    await categories.drop()
    await authors.drop()
    await db.q("DROP TABLE IF EXISTS audit_log")
    await db.close()
    print("   Dropped all tables and views")
    print("   Database closed")
    print()

    print("=" * 70)
    print("Complete example finished successfully!")
    print("All 11 phases demonstrated.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
