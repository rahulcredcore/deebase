"""
Phase 10 Example: Foreign Keys & Defaults

This example demonstrates the enhanced create() method features
implemented in Phase 10, including:
- ForeignKey type annotation for relationships
- Automatic default value extraction from class definitions
- if_not_exists parameter for safe table creation
- replace parameter to drop and recreate tables
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional
from deebase import Database, ForeignKey, Text, IntegrityError


async def main():
    print("=" * 70)
    print("Phase 10: Foreign Keys & Defaults")
    print("=" * 70)
    print()

    # Create in-memory database
    db = Database("sqlite+aiosqlite:///:memory:")

    # =========================================================================
    # 1. Default Values from Class Definitions
    # =========================================================================
    print("1. Default Values")
    print("-" * 70)

    class Article:
        id: int
        title: str
        status: str = "draft"      # SQL DEFAULT 'draft'
        views: int = 0             # SQL DEFAULT 0
        featured: bool = False     # SQL DEFAULT 0 (SQLite)

    articles = await db.create(Article, pk='id')
    print(f"Created table with defaults: {articles._name}")

    # Insert without specifying default fields
    article1 = await articles.insert({"id": 1, "title": "Hello World"})
    print(f"  Inserted (no defaults specified): {article1}")
    print(f"    status = '{article1['status']}' (default)")
    print(f"    views = {article1['views']} (default)")
    print(f"    featured = {article1['featured']} (default)")

    # Insert with explicit values (override defaults)
    article2 = await articles.insert({
        "id": 2,
        "title": "Featured Post",
        "status": "published",
        "views": 100,
        "featured": True
    })
    print(f"  Inserted (explicit values): {article2}")
    print()

    # =========================================================================
    # 2. Dataclass with Defaults
    # =========================================================================
    print("2. Dataclass with Defaults")
    print("-" * 70)

    @dataclass
    class Product:
        id: Optional[int] = None
        name: str = ""
        price: float = 0.0
        in_stock: bool = True
        category: str = "general"

    products = await db.create(Product, pk='id')
    print(f"Created table from dataclass: {products._name}")

    # Insert returns dataclass instances
    product1 = await products.insert({"name": "Widget"})
    print(f"  Inserted: {product1}")
    print(f"    Type: {type(product1).__name__}")
    print(f"    product1.price = {product1.price} (default)")
    print(f"    product1.in_stock = {product1.in_stock} (default)")
    print(f"    product1.category = '{product1.category}' (default)")
    print()

    # =========================================================================
    # 3. Foreign Keys with ForeignKey Type
    # =========================================================================
    print("3. Foreign Keys")
    print("-" * 70)

    # Parent table: Users
    class User:
        id: int
        name: str
        email: str

    users = await db.create(User, pk='id')
    print(f"Created parent table: {users._name}")

    # Child table: Posts with FK to users
    class Post:
        id: int
        title: str
        content: Text
        author_id: ForeignKey[int, "user"]  # FK to user.id

    posts = await db.create(Post, pk='id')
    print(f"Created child table with FK: {posts._name}")

    # Insert a user
    user = await users.insert({"id": 1, "name": "Alice", "email": "alice@example.com"})
    print(f"  Inserted user: {user}")

    # Insert a post referencing the user
    post = await posts.insert({
        "id": 1,
        "title": "My First Post",
        "content": "This is the content...",
        "author_id": 1  # References user.id = 1
    })
    print(f"  Inserted post: id={post['id']}, author_id={post['author_id']}")
    print()

    # =========================================================================
    # 4. FK Constraint Enforcement
    # =========================================================================
    print("4. FK Constraint Enforcement")
    print("-" * 70)

    # Enable FK enforcement for SQLite
    await db.q("PRAGMA foreign_keys = ON")
    print("Enabled FK constraints (PRAGMA foreign_keys = ON)")

    # Try to insert with invalid FK
    try:
        await posts.insert({
            "id": 2,
            "title": "Invalid Post",
            "content": "This should fail",
            "author_id": 999  # Non-existent user!
        })
        print("  ERROR: Should have raised IntegrityError!")
    except IntegrityError as e:
        print(f"  Correctly caught IntegrityError: FK constraint violated")
    print()

    # =========================================================================
    # 5. Multiple Foreign Keys
    # =========================================================================
    print("5. Multiple Foreign Keys")
    print("-" * 70)

    class Category:
        id: int
        name: str

    categories = await db.create(Category, pk='id')
    await categories.insert({"id": 1, "name": "Technology"})
    await categories.insert({"id": 2, "name": "Science"})
    print(f"Created categories table with 2 records")

    class BlogPost:
        id: int
        title: str
        author_id: ForeignKey[int, "user"]
        category_id: ForeignKey[int, "category"]
        status: str = "draft"

    blog_posts = await db.create(BlogPost, pk='id')
    print(f"Created blog_posts with two FKs: author_id -> user, category_id -> category")

    bp = await blog_posts.insert({
        "id": 1,
        "title": "AI in 2025",
        "author_id": 1,
        "category_id": 1
    })
    print(f"  Inserted: id={bp['id']}, author_id={bp['author_id']}, category_id={bp['category_id']}, status='{bp['status']}'")
    print()

    # =========================================================================
    # 6. if_not_exists Parameter
    # =========================================================================
    print("6. if_not_exists Parameter")
    print("-" * 70)

    class Config:
        key: str
        value: str

    # First creation
    config1 = await db.create(Config, pk='key')
    await config1.insert({"key": "app_name", "value": "MyApp"})
    print("Created config table and inserted data")

    # Second creation with if_not_exists - no error!
    config2 = await db.create(Config, pk='key', if_not_exists=True)
    print("Called create() again with if_not_exists=True - no error")

    # Data is preserved
    all_configs = await config2()
    print(f"  Data preserved: {all_configs}")
    print()

    # =========================================================================
    # 7. replace Parameter
    # =========================================================================
    print("7. replace Parameter")
    print("-" * 70)

    class TempData:
        id: int
        data: str

    temp = await db.create(TempData, pk='id')
    await temp.insert({"id": 1, "data": "old data"})
    print(f"Created temp table with data: {await temp()}")

    # Replace drops and recreates
    temp = await db.create(TempData, pk='id', replace=True)
    print("Called create() with replace=True - table recreated")

    all_temp = await temp()
    print(f"  Data after replace: {all_temp} (empty - table was dropped)")
    print()

    # =========================================================================
    # 8. Combining Features
    # =========================================================================
    print("8. Combining All Features")
    print("-" * 70)

    class Author:
        id: int
        name: str
        active: bool = True

    class Publisher:
        id: int
        name: str
        country: str = "USA"

    class Book:
        id: int
        title: str
        author_id: ForeignKey[int, "author"]
        publisher_id: ForeignKey[int, "publisher"]
        price: float = 9.99
        in_print: bool = True

    # Create all tables (safe with if_not_exists)
    authors = await db.create(Author, pk='id', if_not_exists=True)
    publishers = await db.create(Publisher, pk='id', if_not_exists=True)
    books = await db.create(Book, pk='id', if_not_exists=True)
    print("Created authors, publishers, and books tables")

    # Insert data
    await authors.insert({"id": 1, "name": "Jane Doe"})
    await publishers.insert({"id": 1, "name": "Tech Press"})

    book = await books.insert({
        "id": 1,
        "title": "Python Mastery",
        "author_id": 1,
        "publisher_id": 1
        # price and in_print use defaults
    })
    print(f"  Book: {book}")
    print(f"    price = ${book['price']} (default)")
    print(f"    in_print = {book['in_print']} (default)")
    print()

    # =========================================================================
    # Summary
    # =========================================================================
    print("=" * 70)
    print("Summary: Phase 10 Features")
    print("=" * 70)
    print("""
    1. Default values from class definitions:
       status: str = "draft"  → SQL DEFAULT 'draft'

    2. ForeignKey type annotation:
       author_id: ForeignKey[int, "users"]  → FK constraint

    3. if_not_exists parameter:
       await db.create(User, pk='id', if_not_exists=True)

    4. replace parameter:
       await db.create(User, pk='id', replace=True)

    5. Works with both regular classes (→ dicts) and @dataclass (→ instances)
    """)

    await db.close()
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
