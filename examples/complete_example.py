"""
Complete Example: Combining Phase 1 & 2

This example shows a realistic workflow combining:
- Table creation from Python classes (Phase 2)
- Raw SQL queries for data manipulation (Phase 1)
- Schema inspection
- Type safety with rich types
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

    # Insert authors using raw SQL
    print("3. Inserting authors...")
    await db.q("""
        INSERT INTO author (id, name, email, bio) VALUES
        (1, 'Alice Smith', 'alice@example.com', 'Tech writer and blogger'),
        (2, 'Bob Jones', 'bob@example.com', 'Software engineer and author')
    """)
    print("   ✓ 2 authors inserted\n")

    # Insert posts using raw SQL with JSON
    print("4. Inserting posts...")
    await db.q("""
        INSERT INTO post (id, title, slug, content, excerpt, author_id, metadata,
                         published, view_count, created_at)
        VALUES (
            1,
            'Getting Started with DeeBase',
            'getting-started-deebase',
            'This is a comprehensive guide to DeeBase, an async database library...',
            'Learn how to use DeeBase for async database operations',
            1,
            '{"category": "tutorial", "tags": ["python", "async", "database"]}',
            1,
            42,
            '2025-12-23 10:00:00'
        )
    """)

    await db.q("""
        INSERT INTO post (id, title, slug, content, author_id, metadata,
                         published, view_count, created_at)
        VALUES (
            2,
            'Advanced SQLAlchemy Patterns',
            'advanced-sqlalchemy',
            'Explore advanced patterns for using SQLAlchemy with async Python...',
            2,
            '{"category": "advanced", "tags": ["sqlalchemy", "patterns"]}',
            1,
            156,
            '2025-12-22 14:30:00'
        )
    """)
    print("   ✓ 2 posts inserted\n")

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

    # Statistics
    print("7. Blog statistics...")
    stats = await db.q("""
        SELECT
            COUNT(*) as total_posts,
            SUM(view_count) as total_views,
            AVG(view_count) as avg_views_per_post,
            COUNT(DISTINCT author_id) as total_authors
        FROM post
    """)

    stat = stats[0]
    print(f"   Total posts: {stat['total_posts']}")
    print(f"   Total views: {stat['total_views']}")
    print(f"   Average views per post: {stat['avg_views_per_post']:.1f}")
    print(f"   Total authors: {stat['total_authors']}\n")

    # Clean up
    print("8. Cleaning up...")
    await posts.drop()
    await authors.drop()
    await db.close()
    print("   ✓ Database closed\n")

    print("=" * 60)
    print("Complete example finished successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
