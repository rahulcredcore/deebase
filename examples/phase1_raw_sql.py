"""
Phase 1 Example: Raw SQL Queries and Database Connection

This example demonstrates:
- Creating a database connection
- Executing raw SQL queries
- Creating tables with SQL
- Inserting and querying data
- Handling DDL vs DML statements
"""

import asyncio
from deebase import Database


async def main():
    print("=" * 60)
    print("Phase 1: Raw SQL Queries")
    print("=" * 60)
    print()

    # Create in-memory database
    print("1. Creating in-memory database...")
    db = Database("sqlite+aiosqlite:///:memory:")
    print("✓ Database connected\n")

    # Simple SELECT query
    print("2. Running simple SELECT query...")
    result = await db.q("SELECT 1 as num, 'Hello' as message")
    print(f"   Result: {result}")
    print(f"   Type: {type(result[0])}\n")

    # Create table with raw SQL
    print("3. Creating users table...")
    await db.q("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            age INTEGER
        )
    """)
    print("✓ Table created\n")

    # Insert data
    print("4. Inserting users...")
    await db.q("INSERT INTO users (name, email, age) VALUES ('Alice', 'alice@example.com', 30)")
    await db.q("INSERT INTO users (name, email, age) VALUES ('Bob', 'bob@example.com', 25)")
    await db.q("INSERT INTO users (name, email, age) VALUES ('Charlie', 'charlie@example.com', 35)")
    print("✓ 3 users inserted\n")

    # Query all users
    print("5. Querying all users...")
    users = await db.q("SELECT * FROM users ORDER BY name")
    print(f"   Found {len(users)} users:")
    for user in users:
        print(f"   - {user['name']}: {user['email']} (age {user['age']})")
    print()

    # Query with WHERE clause
    print("6. Querying users over 25...")
    older_users = await db.q("SELECT name, age FROM users WHERE age > 25 ORDER BY age")
    print(f"   Found {len(older_users)} users:")
    for user in older_users:
        print(f"   - {user['name']}: {user['age']} years old")
    print()

    # Verify table exists in schema
    print("7. Checking database schema...")
    tables = await db.q("SELECT name FROM sqlite_master WHERE type='table'")
    print(f"   Tables in database: {[t['name'] for t in tables]}\n")

    # Clean up
    print("8. Closing database...")
    await db.close()
    print("✓ Database closed\n")

    print("=" * 60)
    print("Phase 1 example completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
