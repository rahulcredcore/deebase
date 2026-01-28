"""
Phase 18 Example: Full-Text Search (BM25)

This example demonstrates the FTS features implemented in Phase 18:
- FTSIndex class for declaring FTS indexes
- Creating FTS indexes at table creation time and post-creation
- Searching with BM25 ranking
- Column-specific search
- BM25 score retrieval
- FTS sync (insert/update/delete keep FTS in sync via triggers)
- FTS introspection (fts_indexes property)
- Dropping FTS indexes
- Search with xtra() filters
- Search with dataclass support
"""

import asyncio
from deebase import Database, FTSIndex, Text


async def main():
    print("=" * 70)
    print("Phase 18: Full-Text Search (BM25)")
    print("=" * 70)
    print()

    db = Database("sqlite+aiosqlite:///:memory:")

    # =========================================================================
    # 1. Creating a table with an FTS index via db.create()
    # =========================================================================
    print("1. Creating table with FTS index via db.create()")
    print("-" * 70)

    class Article:
        id: int
        title: str
        content: Text
        author: str

    articles = await db.create(Article, pk="id", indexes=[
        FTSIndex("title", "content"),  # FTS on title + content
    ])

    print(f"   Created table: article")
    print(f"   FTS indexes: {articles.fts_indexes}")
    print()

    # =========================================================================
    # 2. Inserting sample data (auto-synced to FTS via triggers)
    # =========================================================================
    print("2. Inserting sample data")
    print("-" * 70)

    sample_articles = [
        {"title": "Getting Started with Python", "content": "Python is a versatile programming language. It is great for beginners and experts alike.", "author": "Alice"},
        {"title": "Advanced Python Patterns", "content": "Decorators, context managers, and metaclasses are powerful Python patterns.", "author": "Alice"},
        {"title": "Introduction to Databases", "content": "Databases store and organize data. SQL is the standard query language for relational databases.", "author": "Bob"},
        {"title": "SQLite Full-Text Search", "content": "SQLite FTS5 provides BM25 ranking for full-text search. It uses inverted indexes for fast lookups.", "author": "Bob"},
        {"title": "Async Programming in Python", "content": "asyncio enables concurrent programming. Use async and await for non-blocking I/O operations.", "author": "Alice"},
        {"title": "Database Design Best Practices", "content": "Normalization, indexing, and query optimization are key to good database design.", "author": "Charlie"},
        {"title": "Building REST APIs", "content": "FastAPI and Flask are popular frameworks for building REST APIs in Python.", "author": "Charlie"},
        {"title": "Machine Learning Basics", "content": "Machine learning uses algorithms to find patterns in data. Python's scikit-learn is a great starting point.", "author": "Alice"},
    ]

    for a in sample_articles:
        await articles.insert(a)
    print(f"   Inserted {len(sample_articles)} articles")
    print()

    # =========================================================================
    # 3. Basic search
    # =========================================================================
    print("3. Basic full-text search")
    print("-" * 70)

    results = await articles.search("python")
    print(f"   Search: 'python' → {len(results)} results")
    for r in results:
        print(f"      - {r['title']}")
    print()

    # =========================================================================
    # 4. Search with limit
    # =========================================================================
    print("4. Search with limit")
    print("-" * 70)

    results = await articles.search("python", limit=3)
    print(f"   Search: 'python' (limit=3) → {len(results)} results")
    for r in results:
        print(f"      - {r['title']}")
    print()

    # =========================================================================
    # 5. Search with BM25 scores
    # =========================================================================
    print("5. Search with BM25 scores")
    print("-" * 70)

    results = await articles.search("python programming", score=True)
    print(f"   Search: 'python programming' (with scores)")
    for record, score in results:
        print(f"      {score:>8.4f}  {record['title']}")
    print("   (More negative = more relevant)")
    print()

    # =========================================================================
    # 6. Column-specific search
    # =========================================================================
    print("6. Column-specific search")
    print("-" * 70)

    # Search only in titles
    results = await articles.search("database", columns=["title"])
    print(f"   Search title only: 'database' → {len(results)} results")
    for r in results:
        print(f"      - {r['title']}")

    # Compare with searching all columns
    results_all = await articles.search("database")
    print(f"   Search all columns: 'database' → {len(results_all)} results")
    for r in results_all:
        print(f"      - {r['title']}")
    print()

    # =========================================================================
    # 7. FTS auto-sync: inserts are searchable immediately
    # =========================================================================
    print("7. FTS auto-sync: new inserts are searchable")
    print("-" * 70)

    await articles.insert({
        "title": "Kubernetes Deployment Guide",
        "content": "Deploy containerized applications with Kubernetes orchestration.",
        "author": "Dave",
    })
    results = await articles.search("kubernetes")
    print(f"   Inserted 'Kubernetes Deployment Guide'")
    print(f"   Search 'kubernetes' → {len(results)} result(s)")
    assert len(results) == 1
    print(f"      - {results[0]['title']}")
    print()

    # =========================================================================
    # 8. FTS auto-sync: updates are reflected
    # =========================================================================
    print("8. FTS auto-sync: updates are reflected")
    print("-" * 70)

    # Find the Kubernetes article and update it
    k8s = await articles.lookup(title="Kubernetes Deployment Guide")
    k8s["title"] = "Docker and Kubernetes Guide"
    await articles.update(k8s)

    results = await articles.search("docker")
    print(f"   Updated title to 'Docker and Kubernetes Guide'")
    print(f"   Search 'docker' → {len(results)} result(s)")
    assert len(results) == 1
    print(f"      - {results[0]['title']}")
    print()

    # =========================================================================
    # 9. FTS auto-sync: deletes are reflected
    # =========================================================================
    print("9. FTS auto-sync: deletes are reflected")
    print("-" * 70)

    await articles.delete(k8s["id"])
    results = await articles.search("kubernetes")
    print(f"   Deleted 'Docker and Kubernetes Guide'")
    print(f"   Search 'kubernetes' → {len(results)} result(s)")
    assert len(results) == 0
    print()

    # =========================================================================
    # 10. Creating a second FTS index post-creation
    # =========================================================================
    print("10. Creating FTS index post-creation")
    print("-" * 70)

    await articles.create_fts_index("title", name="title_only_fts")
    print(f"   Created additional FTS index: title_only_fts")
    print(f"   All FTS indexes: {len(articles.fts_indexes)}")
    for idx in articles.fts_indexes:
        print(f"      {idx['name']}: columns={idx['columns']}")
    print()

    # =========================================================================
    # 11. Dropping an FTS index
    # =========================================================================
    print("11. Dropping an FTS index")
    print("-" * 70)

    await articles.drop_fts_index("title_only_fts")
    print(f"   Dropped: title_only_fts")
    print(f"   Remaining FTS indexes: {len(articles.fts_indexes)}")
    for idx in articles.fts_indexes:
        print(f"      {idx['name']}: columns={idx['columns']}")
    print()

    # =========================================================================
    # 12. Search with xtra() filters
    # =========================================================================
    print("12. Search with xtra() filters")
    print("-" * 70)

    # Search only Alice's articles
    alice_articles = articles.xtra(author="Alice")
    # Copy FTS metadata to filtered table
    alice_articles._fts_indexes = articles._fts_indexes

    results = await alice_articles.search("python")
    print(f"   Search 'python' filtered to author='Alice' → {len(results)} results")
    for r in results:
        print(f"      - {r['title']} (by {r['author']})")
        assert r["author"] == "Alice"
    print()

    # =========================================================================
    # 13. Search with dataclass support
    # =========================================================================
    print("13. Search with dataclass support")
    print("-" * 70)

    ArticleDC = articles.dataclass()
    print(f"   Generated dataclass: {ArticleDC.__name__}")

    results = await articles.search("database")
    print(f"   Search 'database' → {len(results)} results (as dataclass)")
    for r in results:
        # Dataclass attribute access
        print(f"      - {r.title} by {r.author}")
    print()

    # =========================================================================
    # 14. Phrase and multi-word search
    # =========================================================================
    print("14. Multi-word search")
    print("-" * 70)

    results = await articles.search("full-text search", score=True)
    print(f"   Search: 'full-text search' → {len(results)} results")
    for record, score in results:
        print(f"      {score:>8.4f}  {record.title}")
    print()

    # =========================================================================
    # Cleanup
    # =========================================================================
    await articles.drop_fts_index()  # Drop remaining FTS index
    await articles.drop()
    await db.close()

    print("=" * 70)
    print("Phase 18 example finished successfully!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
