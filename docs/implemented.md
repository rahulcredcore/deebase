# DeeBase - Implemented Features

This document provides a detailed guide to what's currently working in DeeBase at each phase of development.

## Phase 1: Core Infrastructure ✅ COMPLETE

### Database Connection

```python
from deebase import Database

# Create database connection
db = Database("sqlite+aiosqlite:///myapp.db")

# Or use in-memory database
db = Database("sqlite+aiosqlite:///:memory:")

# Context manager support
async with Database("sqlite+aiosqlite:///myapp.db") as db:
    results = await db.q("SELECT 1")
```

### Raw SQL Queries

```python
# Execute any SQL query
results = await db.q("SELECT 1 as num")
# Returns: [{'num': 1}]

# Create tables with raw SQL
await db.q("""
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT
    )
""")

# Insert data
await db.q("INSERT INTO users (name, email) VALUES ('Alice', 'alice@example.com')")

# Query data
results = await db.q("SELECT * FROM users")
# Returns: [{'id': 1, 'name': 'Alice', 'email': 'alice@example.com'}]

# DDL/DML statements return empty list
result = await db.q("CREATE TABLE test (id INT)")
# Returns: []
```

### Type System

DeeBase includes a rich type system that maps Python types to database columns:

```python
from deebase import Text
from typing import Optional
from datetime import datetime

class Article:
    # Basic types
    id: int                    # INTEGER
    count: int                 # INTEGER
    price: float              # REAL/FLOAT
    active: bool              # BOOLEAN
    data: bytes               # BLOB/BYTEA

    # String types
    title: str                # VARCHAR (limited string)
    author: str               # VARCHAR

    # Unlimited text
    content: Text             # TEXT (unlimited)
    summary: Text             # TEXT (unlimited)

    # Structured data
    metadata: dict            # JSON (PostgreSQL) / TEXT with serialization (SQLite)
    settings: dict            # JSON

    # Temporal types
    created_at: datetime      # TIMESTAMP/DATETIME
    updated_at: datetime      # TIMESTAMP/DATETIME

    # Nullable fields
    email: Optional[str]      # VARCHAR NULL
    bio: Optional[Text]       # TEXT NULL
    tags: Optional[dict]      # JSON NULL
```

**Type Mappings:**
- `int` → INTEGER
- `str` → VARCHAR (SQLite: TEXT, PostgreSQL: VARCHAR)
- `Text` → TEXT (unlimited in both databases)
- `float` → REAL/FLOAT
- `bool` → BOOLEAN (SQLite: INTEGER 0/1)
- `bytes` → BLOB/BYTEA
- `dict` → JSON (PostgreSQL: JSON, SQLite: TEXT with auto-serialization)
- `datetime` → TIMESTAMP/DATETIME
- `date` → DATE
- `time` → TIME
- `Optional[T]` → Makes column nullable

### Access Underlying SQLAlchemy

```python
# Access the async engine
engine = db.engine

# Close database connection
await db.close()
```

### Testing

- 62 passing tests covering all Phase 1 functionality
- Async test infrastructure with pytest-asyncio
- In-memory SQLite fixtures for fast testing

---

## Phase 2: Table Creation & Schema ✅ COMPLETE

### Create Tables from Python Classes

```python
from deebase import Database, Text
from typing import Optional
from datetime import datetime

db = Database("sqlite+aiosqlite:///myapp.db")

# Simple table
class User:
    id: int
    name: str
    email: str

users = await db.create(User, pk='id')
```

### Rich Type Support

```python
# Table with Text and JSON columns
class Article:
    id: int
    title: str              # VARCHAR (short string)
    slug: str               # VARCHAR
    content: Text           # TEXT (unlimited)
    metadata: dict          # JSON column
    created_at: datetime    # TIMESTAMP

articles = await db.create(Article, pk='id')
```

### Optional/Nullable Fields

```python
class User:
    id: int                      # NOT NULL (primary key)
    name: str                    # NOT NULL (required)
    email: Optional[str]         # NULL (optional)
    bio: Optional[Text]          # NULL (optional)
    preferences: Optional[dict]  # NULL (optional)

users = await db.create(User, pk='id')

# Verify nullable properties
assert users.sa_table.c['id'].nullable is False
assert users.sa_table.c['name'].nullable is False
assert users.sa_table.c['email'].nullable is True
```

### Primary Key Configuration

```python
# Default primary key (uses 'id')
class Product:
    id: int
    name: str
    price: float

products = await db.create(Product)  # pk='id' is default

# Custom primary key
class Item:
    item_id: int
    name: str

items = await db.create(Item, pk='item_id')

# Composite primary key
class OrderItem:
    order_id: int
    product_id: int
    quantity: int

order_items = await db.create(OrderItem, pk=['order_id', 'product_id'])
```

### Table Schema

```python
class User:
    id: int
    name: str
    email: Optional[str]

users = await db.create(User, pk='id')

# Get CREATE TABLE SQL
schema = users.schema
print(schema)
# Output:
# CREATE TABLE user (
#   id INTEGER NOT NULL,
#   name VARCHAR NOT NULL,
#   email VARCHAR,
#   PRIMARY KEY (id)
# )
```

### Drop Tables

```python
# Create a table
class TempTable:
    id: int
    value: str

temp = await db.create(TempTable, pk='id')

# Drop the table
await temp.drop()

# Table is now removed from database
```

### Access SQLAlchemy Objects

```python
users = await db.create(User, pk='id')

# Access underlying SQLAlchemy Table
sa_table = users.sa_table

# Access columns
id_column = users.sa_table.c['id']
name_column = users.sa_table.c['name']

# Access primary key
pk_columns = users.sa_table.primary_key
```

### Table Caching

```python
# Tables are cached after creation
users = await db.create(User, pk='id')

# Get from cache
cached_users = db._get_table('user')
assert cached_users is users
```

### Complete Example

```python
from deebase import Database, Text
from typing import Optional
from datetime import datetime

async def main():
    # Create database
    db = Database("sqlite+aiosqlite:///blog.db")

    # Define table structure
    class Article:
        id: int
        title: str                      # VARCHAR (short string)
        slug: str                       # VARCHAR
        author: str                     # VARCHAR
        content: Text                   # TEXT (unlimited)
        excerpt: Optional[str]          # VARCHAR NULL
        metadata: dict                  # JSON
        published: bool                 # BOOLEAN
        view_count: int                 # INTEGER
        created_at: datetime            # TIMESTAMP
        updated_at: Optional[datetime]  # TIMESTAMP NULL

    # Create table
    articles = await db.create(Article, pk='id')

    # View schema
    print(articles.schema)

    # Access SQLAlchemy objects
    print(f"Table name: {articles.sa_table.name}")
    print(f"Columns: {list(articles.sa_table.columns.keys())}")
    print(f"Primary key: {[c.name for c in articles.sa_table.primary_key]}")

    # Clean up
    await articles.drop()
    await db.close()

# Run
import asyncio
asyncio.run(main())
```

### Testing

- 78 total passing tests (62 from Phase 1 + 16 new)
- Complete test coverage for:
  - Table creation with all type combinations
  - Text and JSON column types
  - Optional/nullable fields
  - Primary key configurations (default, custom, composite)
  - Schema generation
  - Table dropping
  - Error handling

---

## What's Next: Phase 3 - CRUD Operations

Coming soon:
- `table.insert()` - Insert records
- `table.update()` - Update records
- `table.upsert()` - Insert or update
- `table.delete()` - Delete records
- `table()` - Select all/limited records
- `table[pk]` - Get by primary key
- `table.lookup()` - Query with WHERE conditions

All operations will support both dict and dataclass modes.

---

## Error Handling

```python
# No type annotations
class Empty:
    pass

await db.create(Empty)
# Raises: ValueError: Class Empty has no type annotations

# Invalid primary key
class User:
    id: int
    name: str

await db.create(User, pk='user_id')
# Raises: ValueError: Primary key column 'user_id' not found in class annotations

# Drop non-existent table twice
temp = await db.create(TempTable, pk='id')
await temp.drop()
await temp.drop()
# Raises: SQLAlchemy exception (table doesn't exist)
```

---

## Dependencies

- Python 3.14+
- sqlalchemy 2.0.45+ (with async support)
- aiosqlite 0.22.0+ (async SQLite driver)
- greenlet 3.3.0+ (required for SQLAlchemy async)
- pytest + pytest-asyncio (for testing)

---

## Database Support

Currently tested with:
- ✅ SQLite (via aiosqlite)
- 🚧 PostgreSQL (via asyncpg) - infrastructure ready, not yet tested

The codebase is designed to be database-agnostic through SQLAlchemy's dialect system.
