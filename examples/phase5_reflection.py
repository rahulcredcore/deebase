"""
Phase 5 Example: Dynamic Access & Reflection

This example demonstrates Phase 5 reflection features:
- Reflecting existing tables with db.reflect()
- Single table reflection with db.reflect_table()
- Dynamic table access via db.t.tablename
- Multiple table access
- Working with existing databases
- Mixed workflows (db.create() + raw SQL + reflection)
"""

import asyncio
from deebase import Database


async def main():
    print("=" * 70)
    print("Phase 5: Dynamic Access & Reflection")
    print("=" * 70)
    print()

    # Create in-memory database
    db = Database("sqlite+aiosqlite:///:memory:")

    # =========================================================================
    # 1. Reflect Tables Created with Raw SQL
    # =========================================================================
    print("1. Reflecting Tables from Raw SQL")
    print("-" * 70)

    # Create tables with raw SQL (simulating existing database)
    await db.q("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            country TEXT
        )
    """)

    await db.q("""
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            total REAL NOT NULL,
            status TEXT DEFAULT 'pending'
        )
    """)

    await db.q("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER DEFAULT 0
        )
    """)

    print("✓ Created 3 tables with raw SQL:")
    print("  • customers")
    print("  • orders")
    print("  • products")
    print()

    # Before reflection - db.t.customers doesn't work
    print("Before reflection:")
    try:
        _ = db.t.customers
    except AttributeError as e:
        print(f"  • db.t.customers raises: {str(e)[:60]}...")
    print()

    # Reflect all tables from database
    print("Calling db.reflect()...")
    await db.reflect()
    print("✓ Reflected all tables from database")
    print()

    # After reflection - db.t.customers works!
    print("After reflection:")
    customers = db.t.customers
    orders = db.t.orders
    products = db.t.products
    print(f"  • db.t.customers: {customers._name}")
    print(f"  • db.t.orders: {orders._name}")
    print(f"  • db.t.products: {products._name}")
    print()

    # =========================================================================
    # 2. Dynamic Table Access
    # =========================================================================
    print("\n2. Dynamic Table Access")
    print("-" * 70)

    # Access by attribute
    print("Access by attribute (db.t.tablename):")
    customers = db.t.customers
    print(f"  • db.t.customers → {customers._name}")
    print()

    # Access by index
    print("Access by index (db.t['tablename']):")
    orders = db.t['orders']
    print(f"  • db.t['orders'] → {orders._name}")
    print()

    # Multiple table access
    print("Multiple table access:")
    customers, orders, products = db.t['customers', 'orders', 'products']
    print(f"  • db.t['customers', 'orders', 'products']")
    print(f"    → {customers._name}, {orders._name}, {products._name}")
    print()

    # =========================================================================
    # 3. CRUD on Reflected Tables
    # =========================================================================
    print("\n3. CRUD Operations on Reflected Tables")
    print("-" * 70)

    # Insert customers
    print("INSERT customers:")
    alice = await customers.insert({"name": "Alice", "email": "alice@example.com", "country": "USA"})
    bob = await customers.insert({"name": "Bob", "email": "bob@example.com", "country": "UK"})
    print(f"  • {alice}")
    print(f"  • {bob}")
    print()

    # Insert products
    print("INSERT products:")
    widget = await products.insert({"name": "Widget", "price": 9.99, "stock": 100})
    gadget = await products.insert({"name": "Gadget", "price": 14.99, "stock": 50})
    print(f"  • {widget}")
    print(f"  • {gadget}")
    print()

    # Insert orders
    print("INSERT orders:")
    order1 = await orders.insert({"customer_id": alice['id'], "total": 99.99, "status": "completed"})
    order2 = await orders.insert({"customer_id": bob['id'], "total": 149.99, "status": "pending"})
    print(f"  • Order {order1['id']}: ${order1['total']} ({order1['status']})")
    print(f"  • Order {order2['id']}: ${order2['total']} ({order2['status']})")
    print()

    # SELECT
    print("SELECT all customers:")
    all_customers = await customers()
    for c in all_customers:
        print(f"  • {c['name']} ({c['country']})")
    print()

    # LOOKUP
    print("LOOKUP customer by email:")
    found = await customers.lookup(email="alice@example.com")
    print(f"  • Found: {found['name']}")
    print()

    # =========================================================================
    # 4. Single Table Reflection
    # =========================================================================
    print("\n4. Single Table Reflection")
    print("-" * 70)

    # Create a new table with raw SQL
    print("Creating new table with raw SQL...")
    await db.q("""
        CREATE TABLE reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT
        )
    """)
    print("✓ Created 'reviews' table")
    print()

    # Reflect just this table
    print("Reflecting single table:")
    reviews = await db.reflect_table('reviews')
    print(f"  • await db.reflect_table('reviews') → {reviews._name}")
    print()

    # Now db.t.reviews works
    print("Access via db.t:")
    reviews_via_t = db.t.reviews
    print(f"  • db.t.reviews → {reviews_via_t._name}")
    print(f"  • Same instance: {reviews is reviews_via_t}")
    print()

    # Use it
    review = await reviews.insert({
        "product_id": widget['id'],
        "rating": 5,
        "comment": "Great product!"
    })
    print(f"Inserted review: {review}")
    print()

    # =========================================================================
    # 5. Mixed Workflow: db.create() + Reflection
    # =========================================================================
    print("\n5. Mixed Workflow")
    print("-" * 70)

    # Create a new database for this example
    db2 = Database("sqlite+aiosqlite:///:memory:")

    # Create one table via db.create()
    print("Create table via db.create():")
    class User:
        id: int
        name: str
        role: str

    users = await db2.create(User, pk='id')
    print(f"  • Created: {users._name}")
    print()

    # Create another with raw SQL
    print("Create table via raw SQL:")
    await db2.q("CREATE TABLE sessions (id INTEGER PRIMARY KEY, user_id INTEGER, token TEXT)")
    print("  • Created: sessions")
    print()

    # Reflect to pick up raw SQL table
    print("Calling db.reflect()...")
    await db2.reflect()
    print("✓ Reflected")
    print()

    # Access both via db.t
    print("Access via db.t:")
    users_via_t = db2.t.user  # From db.create() (was already cached)
    sessions = db2.t.sessions  # From reflection
    print(f"  • db.t.user (from create): {users_via_t._name}")
    print(f"  • db.t.sessions (from reflect): {sessions._name}")
    print(f"  • Same user instance: {users is users_via_t}")
    print()

    # Both support CRUD
    await users.insert({"name": "Alice", "role": "admin"})
    await sessions.insert({"user_id": 1, "token": "abc123"})
    print("✓ CRUD works on both tables")
    print()

    # =========================================================================
    # 6. Schema Inspection on Reflected Tables
    # =========================================================================
    print("\n6. Schema Inspection")
    print("-" * 70)

    # Inspect reflected table schema
    print("Customers table schema:")
    print(customers.schema)
    print()

    print("Available columns:")
    for col in customers.sa_table.columns:
        print(f"  • {col.name}: {col.type} (nullable={col.nullable})")
    print()

    # Primary key
    pk_cols = list(customers.sa_table.primary_key.columns)
    print(f"Primary key: {[col.name for col in pk_cols]}")
    print()

    # Clean up
    await db.close()
    await db2.close()

    print("\n" + "=" * 70)
    print("Phase 5 Reflection - Complete!")
    print("=" * 70)
    print()
    print("Key Takeaways:")
    print("  • db.reflect() loads all tables (explicit async call)")
    print("  • db.reflect_table(name) loads single table")
    print("  • db.t.tablename is fast sync cache access")
    print("  • db.create() tables are auto-cached (no reflection needed)")
    print("  • Full CRUD works on all reflected tables")


if __name__ == "__main__":
    asyncio.run(main())
