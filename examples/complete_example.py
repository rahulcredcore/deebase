"""
Complete Example: Building a Blog Database

This example shows a realistic workflow combining all phases:
- Table creation from Python classes (Phase 2)
- CRUD operations with rich types (Phase 3)
- Schema inspection
- Type safety with Text, JSON, datetime
"""

import asyncio
from typing import Optional
from datetime import datetime
from deebase import Database, Text


async def main():
    print("=" * 60)
    print("Complete Example: Building a Blog Database")
    print("=" * 60)
    print()

    # Initialize database
    db = Database("sqlite+aiosqlite:///:memory:")

    # Define schema with Python classes
    print("1. Defining schema...")

    class Author:
        id: int
        name: str
        email: str
        bio: Optional[Text]

    class Post:
        id: int
        title: str
        slug: str
        content: Text
        excerpt: Optional[str]
        author_id: int
        metadata: dict
        published: bool
        view_count: int
        created_at: datetime
        updated_at: Optional[datetime]

    print("   ✓ Schema defined\n")

    # Create tables
    print("2. Creating tables...")
    authors = await db.create(Author, pk='id')
    posts = await db.create(Post, pk='id')
    print(f"   ✓ Created: {authors._name}, {posts._name}\n")

    # Insert authors using CRUD
    print("3. Inserting authors...")
    author1 = await authors.insert({
        "name": "Alice Smith",
        "email": "alice@example.com",
        "bio": "Tech writer and blogger"
    })
    author2 = await authors.insert({
        "name": "Bob Jones",
        "email": "bob@example.com",
        "bio": "Software engineer and author"
    })
    print(f"   ✓ 2 authors inserted (IDs: {author1['id']}, {author2['id']})\n")

    # Insert posts using CRUD with rich types (Text, dict/JSON, datetime)
    print("4. Inserting posts...")
    post1 = await posts.insert({
        "title": "Getting Started with DeeBase",
        "slug": "getting-started-deebase",
        "content": "This is a comprehensive guide to DeeBase, an async database library...",
        "excerpt": "Learn how to use DeeBase for async database operations",
        "author_id": author1['id'],
        "metadata": {
            "category": "tutorial",
            "tags": ["python", "async", "database"]
        },
        "published": True,
        "view_count": 42,
        "created_at": datetime(2025, 12, 23, 10, 0, 0)
    })

    post2 = await posts.insert({
        "title": "Advanced SQLAlchemy Patterns",
        "slug": "advanced-sqlalchemy",
        "content": "Explore advanced patterns for using SQLAlchemy with async Python...",
        "author_id": author2['id'],
        "metadata": {
            "category": "advanced",
            "tags": ["sqlalchemy", "patterns"]
        },
        "published": True,
        "view_count": 156,
        "created_at": datetime(2025, 12, 22, 14, 30, 0)
    })
    print(f"   ✓ 2 posts inserted (IDs: {post1['id']}, {post2['id']})\n")

    # Query data with SQL
    print("5. Querying blog posts...")
    results = await db.q("""
        SELECT
            p.title,
            p.excerpt,
            p.view_count,
            a.name as author_name,
            p.metadata
        FROM post p
        JOIN author a ON p.author_id = a.id
        WHERE p.published = 1
        ORDER BY p.view_count DESC
    """)

    print(f"   Found {len(results)} published posts:\n")
    for post in results:
        print(f"   📝 {post['title']}")
        print(f"      By: {post['author_name']}")
        print(f"      Views: {post['view_count']}")
        if post['excerpt']:
            print(f"      Excerpt: {post['excerpt']}")
        print(f"      Metadata: {post['metadata']}")
        print()

    # View schemas
    print("6. Table schemas:")
    print("\nAuthor table:")
    print(authors.schema)
    print("\nPost table:")
    print(posts.schema)
    print()

    # CRUD operations demo
    print("7. Demonstrating CRUD operations...")

    # Lookup by slug
    found_post = await posts.lookup(slug="getting-started-deebase")
    print(f"   • Found post by slug: {found_post['title']}")

    # Update view count
    found_post['view_count'] += 10
    updated_post = await posts.update(found_post)
    print(f"   • Updated view count: {updated_post['view_count']}")

    # Get by primary key
    fetched = await posts[post2['id']]
    print(f"   • Fetched by PK: {fetched['title']}")

    # Select all with limit
    limited = await posts(limit=1)
    print(f"   • Selected with limit(1): {limited[0]['title']}\n")

    # Statistics
    print("8. Blog statistics...")
    all_posts = await posts()
    all_authors = await authors()
    total_views = sum(p['view_count'] for p in all_posts)
    avg_views = total_views / len(all_posts) if all_posts else 0

    print(f"   Total posts: {len(all_posts)}")
    print(f"   Total views: {total_views}")
    print(f"   Average views per post: {avg_views:.1f}")
    print(f"   Total authors: {len(all_authors)}\n")

    # Clean up
    print("9. Cleaning up...")
    await posts.drop()
    await authors.drop()
    await db.close()
    print("   ✓ Database closed\n")

    print("=" * 60)
    print("Complete example finished successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
