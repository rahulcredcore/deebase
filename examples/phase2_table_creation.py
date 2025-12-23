"""
Phase 2 Example: Table Creation from Python Classes

This example demonstrates:
- Creating tables from Python class annotations
- Rich type support (str, Text, dict/JSON, datetime)
- Optional fields and nullable columns
- Primary key configuration
- Schema inspection
- Table dropping
"""

import asyncio
from typing import Optional
from datetime import datetime
from deebase import Database, Text


async def main():
    print("=" * 60)
    print("Phase 2: Table Creation from Python Classes")
    print("=" * 60)
    print()

    # Create in-memory database
    print("1. Creating in-memory database...")
    db = Database("sqlite+aiosqlite:///:memory:")
    print("✓ Database connected\n")

    # Example 1: Simple table
    print("2. Creating simple users table...")

    class User:
        id: int
        name: str
        email: str
        age: int

    users = await db.create(User, pk='id')
    print(f"✓ Table '{users._name}' created")
    print(f"   Columns: {list(users.sa_table.columns.keys())}\n")

    # Example 2: Table with rich types
    print("3. Creating articles table with rich types...")

    class Article:
        id: int
        title: str              # VARCHAR
        slug: str               # VARCHAR
        content: Text           # TEXT (unlimited)
        metadata: dict          # JSON
        view_count: int         # INTEGER
        created_at: datetime    # TIMESTAMP

    articles = await db.create(Article, pk='id')
    print(f"✓ Table '{articles._name}' created")
    print(f"   Columns: {list(articles.sa_table.columns.keys())}")
    print(f"   Column types:")
    for col in articles.sa_table.columns:
        print(f"   - {col.name}: {col.type} (nullable={col.nullable})")
    print()

    # Example 3: Table with optional fields
    print("4. Creating products table with optional fields...")

    class Product:
        id: int
        name: str
        description: Optional[str]      # Nullable VARCHAR
        price: float
        details: Optional[Text]         # Nullable TEXT
        specs: Optional[dict]           # Nullable JSON

    products = await db.create(Product, pk='id')
    print(f"✓ Table '{products._name}' created")
    print(f"   Nullable columns:")
    for col in products.sa_table.columns:
        if col.nullable:
            print(f"   - {col.name}: {col.type}")
    print()

    # Example 4: Composite primary key
    print("5. Creating order_items table with composite PK...")

    class OrderItem:
        order_id: int
        product_id: int
        quantity: int
        price: float

    order_items = await db.create(OrderItem, pk=['order_id', 'product_id'])
    print(f"✓ Table '{order_items._name}' created")
    print(f"   Primary key columns: {[col.name for col in order_items.sa_table.primary_key]}\n")

    # Schema inspection
    print("6. Inspecting table schemas...")
    print("\nUsers table schema:")
    print(users.schema)
    print("\nArticles table schema:")
    print(articles.schema)
    print()

    # List all tables
    print("7. Listing all tables in database...")
    all_tables = await db.q("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    print(f"   Tables: {[t['name'] for t in all_tables]}\n")

    # Column access
    print("8. Accessing columns via ColumnAccessor...")
    print(f"   Articles columns:")
    for col in articles.c:
        print(f"   - {col.name}: {col.type}")
    print()

    # Drop a table
    print("9. Dropping order_items table...")
    await order_items.drop()
    remaining_tables = await db.q("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    print(f"   Remaining tables: {[t['name'] for t in remaining_tables]}\n")

    # Access SQLAlchemy objects
    print("10. Accessing underlying SQLAlchemy objects...")
    print(f"   Engine: {type(db.engine).__name__}")
    print(f"   Metadata: {type(db._metadata).__name__}")
    print(f"   Articles sa_table: {type(articles.sa_table).__name__}")
    print()

    # Clean up
    print("11. Closing database...")
    await db.close()
    print("✓ Database closed\n")

    print("=" * 60)
    print("Phase 2 example completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
