"""
Phase 11 Example: Foreign Key Navigation

This example demonstrates the FK navigation features implemented in Phase 11:
- table.foreign_keys property - list FK definitions
- table.fk.column(record) - convenience API for forward navigation
- table.get_parent(record, fk_column) - power user API for forward navigation
- table.get_children(record, child_table, fk_column) - reverse navigation
"""

import asyncio
from deebase import Database, ForeignKey, Text


async def main():
    print("=" * 70)
    print("Phase 11: Foreign Key Navigation")
    print("=" * 70)
    print()

    # Create in-memory database
    db = Database("sqlite+aiosqlite:///:memory:")

    # Enable FK enforcement
    await db.q("PRAGMA foreign_keys = ON")

    # =========================================================================
    # Setup: Create tables with FK relationships
    # =========================================================================
    print("Setup: Creating tables with FK relationships")
    print("-" * 70)

    class Author:
        id: int
        name: str
        email: str

    class Category:
        id: int
        name: str
        description: str

    class Post:
        id: int
        author_id: ForeignKey[int, "author"]
        category_id: ForeignKey[int, "category"]
        title: str
        content: Text

    class Comment:
        id: int
        post_id: ForeignKey[int, "post"]
        author_id: ForeignKey[int, "author"]
        content: str

    # Create tables in order (parents first)
    authors = await db.create(Author, pk='id')
    categories = await db.create(Category, pk='id')
    posts = await db.create(Post, pk='id')
    comments = await db.create(Comment, pk='id')

    print(f"  Created: {authors._name}, {categories._name}, {posts._name}, {comments._name}")

    # Insert sample data
    alice = await authors.insert({"name": "Alice", "email": "alice@example.com"})
    bob = await authors.insert({"name": "Bob", "email": "bob@example.com"})

    tech = await categories.insert({"name": "Technology", "description": "Tech topics"})
    life = await categories.insert({"name": "Lifestyle", "description": "Life topics"})

    post1 = await posts.insert({
        "author_id": alice["id"],
        "category_id": tech["id"],
        "title": "Intro to Python",
        "content": "Python is a great language..."
    })
    post2 = await posts.insert({
        "author_id": alice["id"],
        "category_id": life["id"],
        "title": "Work-Life Balance",
        "content": "Finding balance is important..."
    })
    post3 = await posts.insert({
        "author_id": bob["id"],
        "category_id": tech["id"],
        "title": "Async Programming",
        "content": "Async/await makes concurrency easier..."
    })

    await comments.insert({
        "post_id": post1["id"],
        "author_id": bob["id"],
        "content": "Great introduction!"
    })
    await comments.insert({
        "post_id": post1["id"],
        "author_id": alice["id"],
        "content": "Thanks Bob!"
    })
    await comments.insert({
        "post_id": post3["id"],
        "author_id": alice["id"],
        "content": "Nice async tutorial!"
    })

    print("  Inserted: 2 authors, 2 categories, 3 posts, 3 comments")
    print()

    # =========================================================================
    # 1. foreign_keys Property
    # =========================================================================
    print("1. foreign_keys Property")
    print("-" * 70)

    print(f"  posts.foreign_keys:")
    for fk in posts.foreign_keys:
        print(f"    {fk['column']} -> {fk['references']}")

    print(f"\n  authors.foreign_keys:")
    fks = authors.foreign_keys
    if not fks:
        print("    (none - authors has no FKs)")

    print(f"\n  comments.foreign_keys:")
    for fk in comments.foreign_keys:
        print(f"    {fk['column']} -> {fk['references']}")
    print()

    # =========================================================================
    # 2. Convenience API: table.fk.column(record)
    # =========================================================================
    print("2. Convenience API: table.fk.column(record)")
    print("-" * 70)

    # Get a post and navigate to its author
    post = await posts[1]
    print(f"  Post: '{post['title']}'")

    # Navigate to author using convenience syntax
    author = await posts.fk.author_id(post)
    print(f"  Author (via posts.fk.author_id): {author['name']}")

    # Navigate to category
    category = await posts.fk.category_id(post)
    print(f"  Category (via posts.fk.category_id): {category['name']}")
    print()

    # =========================================================================
    # 3. Power User API: table.get_parent(record, fk_column)
    # =========================================================================
    print("3. Power User API: table.get_parent(record, fk_column)")
    print("-" * 70)

    # Get comments and their related records
    comment = await comments[1]
    print(f"  Comment: '{comment['content']}'")

    # Navigate to post
    parent_post = await comments.get_parent(comment, "post_id")
    print(f"  Post (via get_parent): '{parent_post['title']}'")

    # Navigate to comment author
    comment_author = await comments.get_parent(comment, "author_id")
    print(f"  Comment author (via get_parent): {comment_author['name']}")
    print()

    # =========================================================================
    # 4. Reverse Navigation: table.get_children()
    # =========================================================================
    print("4. Reverse Navigation: table.get_children()")
    print("-" * 70)

    # Get all posts by Alice
    alice_record = await authors.lookup(name="Alice")
    alice_posts = await authors.get_children(alice_record, "post", "author_id")
    print(f"  Alice's posts ({len(alice_posts)} found):")
    for p in alice_posts:
        print(f"    - '{p['title']}'")

    # Get all comments on post 1
    post1_record = await posts[1]
    post_comments = await posts.get_children(post1_record, "comment", "post_id")
    print(f"\n  Comments on '{post1_record['title']}' ({len(post_comments)} found):")
    for c in post_comments:
        print(f"    - '{c['content']}'")
    print()

    # =========================================================================
    # 5. Using Table Object in get_children()
    # =========================================================================
    print("5. Using Table Object in get_children()")
    print("-" * 70)

    # Can pass Table object instead of string name
    alice_posts2 = await authors.get_children(alice_record, posts, "author_id")
    print(f"  Using string: await authors.get_children(alice, 'post', 'author_id')")
    print(f"  Using Table:  await authors.get_children(alice, posts, 'author_id')")
    print(f"  Both return {len(alice_posts2)} posts")
    print()

    # =========================================================================
    # 6. Handling None and Missing Parents
    # =========================================================================
    print("6. Handling None and Missing Parents")
    print("-" * 70)

    # Dangling FK test (disable FK enforcement first)
    await db.q("PRAGMA foreign_keys = OFF")

    # Create a post with non-existent author
    orphan_post = await posts.insert({
        "author_id": 999,  # Non-existent!
        "category_id": tech["id"],
        "title": "Orphan Post",
        "content": "No author exists..."
    })

    # get_parent returns None for dangling FK
    orphan_author = await posts.get_parent(orphan_post, "author_id")
    print(f"  Orphan post author_id: {orphan_post['author_id']}")
    print(f"  get_parent result: {orphan_author} (None = parent not found)")

    # Re-enable FK enforcement
    await db.q("PRAGMA foreign_keys = ON")
    print()

    # =========================================================================
    # 7. With Dataclass Support
    # =========================================================================
    print("7. With Dataclass Support")
    print("-" * 70)

    # Enable dataclass mode on authors
    AuthorDC = authors.dataclass()
    print(f"  Enabled dataclass mode on authors")

    # Now get_parent returns dataclass instances
    post = await posts[1]
    author_dc = await posts.get_parent(post, "author_id")
    print(f"  Author type: {type(author_dc).__name__}")
    print(f"  Author.name: {author_dc.name}")  # Field access!
    print(f"  Author.email: {author_dc.email}")
    print()

    # =========================================================================
    # 8. Chaining Navigation
    # =========================================================================
    print("8. Chaining Navigation")
    print("-" * 70)

    # Start from a comment, navigate to post, then to post's author
    comment = await comments[1]
    print(f"  Starting from comment: '{comment['content']}'")

    # Navigate: comment -> post -> author
    parent_post = await comments.get_parent(comment, "post_id")
    post_author = await posts.get_parent(parent_post, "author_id")
    print(f"  Comment's post: '{parent_post['title']}'")
    print(f"  Post's author: {post_author.name}")

    # Navigate: comment -> comment's author (different from post's author)
    comment_author = await comments.get_parent(comment, "author_id")
    print(f"  Comment's author: {comment_author.name}")
    print()

    # =========================================================================
    # Summary
    # =========================================================================
    print("=" * 70)
    print("Summary: Phase 11 FK Navigation APIs")
    print("=" * 70)
    print("""
    CONVENIENCE API (recommended for most use cases):
        author = await posts.fk.author_id(post)

    POWER USER API (full control):
        author = await posts.get_parent(post, "author_id")
        user_posts = await users.get_children(user, "post", "author_id")

    FK METADATA:
        posts.foreign_keys  # List of {'column': ..., 'references': ...}

    KEY BEHAVIORS:
        - Returns None if FK value is None or parent not found
        - Respects target table's dataclass setting
        - get_children accepts string name or Table object
        - Works with reflected tables
    """)

    await db.close()
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
