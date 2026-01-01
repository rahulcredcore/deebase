"""
Phase 12 Example: Indexes

This example demonstrates the index features implemented in Phase 12:
- Index class for named indexes
- indexes parameter in db.create()
- table.create_index() for adding indexes after table creation
- table.drop_index() for removing indexes
- table.indexes property for listing indexes
"""

import asyncio
from deebase import Database, Index, IntegrityError


async def main():
    print("=" * 70)
    print("Phase 12: Indexes")
    print("=" * 70)
    print()

    # Create in-memory database
    db = Database("sqlite+aiosqlite:///:memory:")

    # =========================================================================
    # 1. Creating Indexes with db.create()
    # =========================================================================
    print("1. Creating Indexes with db.create()")
    print("-" * 70)

    class Article:
        id: int
        title: str
        slug: str
        author_id: int
        category_id: int
        views: int
        created_at: str

    # Create table with indexes using different syntaxes
    articles = await db.create(
        Article,
        pk='id',
        indexes=[
            "slug",                                         # Simple index (string)
            ("author_id", "created_at"),                    # Composite index (tuple)
            Index("idx_title_unique", "title", unique=True),  # Named unique index
            Index("idx_category_views", "category_id", "views"),  # Named composite
        ]
    )

    print("  Created table 'article' with indexes:")
    for idx in articles.indexes:
        unique_str = " (UNIQUE)" if idx['unique'] else ""
        print(f"    - {idx['name']}: {idx['columns']}{unique_str}")
    print()

    # =========================================================================
    # 2. Index Class
    # =========================================================================
    print("2. Index Class")
    print("-" * 70)

    # Various ways to create Index objects
    idx1 = Index("idx_simple", "column1")
    print(f"  Simple index: {idx1}")

    idx2 = Index("idx_unique", "email", unique=True)
    print(f"  Unique index: {idx2}")

    idx3 = Index("idx_composite", "col1", "col2", "col3")
    print(f"  Composite index: {idx3}")

    idx4 = Index("idx_composite_unique", "a", "b", unique=True)
    print(f"  Composite unique: {idx4}")
    print()

    # =========================================================================
    # 3. Auto-generated Index Names
    # =========================================================================
    print("3. Auto-generated Index Names")
    print("-" * 70)

    class User:
        id: int
        name: str
        email: str

    users = await db.create(
        User,
        pk='id',
        indexes=["name", "email"]  # Auto-named as ix_user_name, ix_user_email
    )

    print("  Auto-generated names follow pattern: ix_{tablename}_{columns}")
    for idx in users.indexes:
        print(f"    - {idx['name']}: {idx['columns']}")
    print()

    # =========================================================================
    # 4. Adding Indexes After Table Creation
    # =========================================================================
    print("4. Adding Indexes After Table Creation")
    print("-" * 70)

    class Product:
        id: int
        name: str
        sku: str
        price: float

    products = await db.create(Product, pk='id')  # No initial indexes
    print(f"  Initial indexes: {products.indexes}")

    # Add index on name
    await products.create_index("name")
    print(f"  After create_index('name'): {[i['name'] for i in products.indexes]}")

    # Add unique index on sku with custom name
    await products.create_index("sku", name="idx_product_sku", unique=True)
    print(f"  After create_index('sku', name='idx_product_sku', unique=True): {[i['name'] for i in products.indexes]}")

    # Add composite index
    await products.create_index(["name", "price"])
    print(f"  After create_index(['name', 'price']): {[i['name'] for i in products.indexes]}")
    print()

    # =========================================================================
    # 5. Dropping Indexes
    # =========================================================================
    print("5. Dropping Indexes")
    print("-" * 70)

    print(f"  Before drop: {[i['name'] for i in products.indexes]}")

    # Drop an index
    await products.drop_index("ix_product_name")
    print(f"  After drop_index('ix_product_name'): (index dropped)")
    print()

    # =========================================================================
    # 6. Unique Index Enforcement
    # =========================================================================
    print("6. Unique Index Enforcement")
    print("-" * 70)

    class Customer:
        id: int
        email: str
        name: str

    customers = await db.create(
        Customer,
        pk='id',
        indexes=[Index("idx_customer_email", "email", unique=True)]
    )

    # Insert first customer
    await customers.insert({"id": 1, "email": "alice@example.com", "name": "Alice"})
    print("  Inserted customer with email: alice@example.com")

    # Try to insert duplicate email
    try:
        await customers.insert({"id": 2, "email": "alice@example.com", "name": "Bob"})
        print("  ERROR: Duplicate insert should have failed!")
    except IntegrityError:
        print("  IntegrityError raised (as expected) - unique constraint enforced!")
    print()

    # =========================================================================
    # 7. Listing All Indexes
    # =========================================================================
    print("7. Listing All Indexes")
    print("-" * 70)

    print("  articles.indexes:")
    for idx in articles.indexes:
        print(f"    name: {idx['name']}")
        print(f"    columns: {idx['columns']}")
        print(f"    unique: {idx['unique']}")
        print()

    # =========================================================================
    # 8. Indexes with Query Performance
    # =========================================================================
    print("8. Indexes with Query Performance")
    print("-" * 70)

    # Insert some data
    await users.insert({"id": 1, "name": "Alice", "email": "alice@example.com"})
    await users.insert({"id": 2, "name": "Bob", "email": "bob@example.com"})
    await users.insert({"id": 3, "name": "Charlie", "email": "charlie@example.com"})

    # Queries on indexed columns use the index (faster for large datasets)
    user = await users.lookup(name="Bob")
    print(f"  Found user by indexed column 'name': {user['name']} ({user['email']})")

    user = await users.lookup(email="charlie@example.com")
    print(f"  Found user by indexed column 'email': {user['name']} ({user['email']})")
    print()

    # =========================================================================
    # Summary
    # =========================================================================
    print("=" * 70)
    print("Summary: Phase 12 Index APIs")
    print("=" * 70)
    print("""
    CREATING INDEXES DURING TABLE CREATION:
        await db.create(MyClass, pk='id', indexes=[
            "column",                         # Simple index (auto-named)
            ("col1", "col2"),                 # Composite index (auto-named)
            Index("name", "column"),          # Named index
            Index("name", "col", unique=True),  # Named unique index
        ])

    ADDING INDEXES AFTER CREATION:
        await table.create_index("column")                    # Simple
        await table.create_index(["col1", "col2"])            # Composite
        await table.create_index("col", name="custom_name")   # Custom name
        await table.create_index("col", unique=True)          # Unique

    DROPPING INDEXES:
        await table.drop_index("index_name")

    LISTING INDEXES:
        table.indexes  # Returns [{'name': ..., 'columns': [...], 'unique': bool}]

    INDEX NAMING CONVENTION:
        Auto-generated names: ix_{tablename}_{column1}_{column2}
        Example: ix_article_author_id_created_at
    """)

    await db.close()
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
