# DeeBase

**Async SQLAlchemy-based database library with an ergonomic, fastlite-inspired API**

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![SQLAlchemy 2.0+](https://img.shields.io/badge/sqlalchemy-2.0+-green.svg)](https://www.sqlalchemy.org/)
[![Tests](https://img.shields.io/badge/tests-161%20passing-brightgreen.svg)](#)
[![License](https://img.shields.io/badge/license-TBD-lightgrey.svg)](#)

DeeBase provides a simple, intuitive interface for async database operations in Python. Built on SQLAlchemy, it combines the ergonomics of [fastlite](https://fastlite.answer.ai/) with full async/await support and multi-database compatibility.

## Features

- **🚀 Async/Await** - Built for modern async Python (FastAPI, etc.)
- **📝 Ergonomic API** - Simple, intuitive database operations
- **🔒 Type Safety** - Optional dataclass support with IDE autocomplete
- **🎯 Multi-Database** - SQLite and PostgreSQL support
- **🛠️ Rich Types** - Text, JSON, datetime, Optional support
- **⚡ Dynamic Access** - Access tables with `db.t.tablename`
- **🔍 Views Support** - Read-only database views
- **🎨 Error Handling** - 6 specific exception types with rich context
- **📤 Code Generation** - Export schemas as Python dataclasses

## Quick Start

### Installation

```bash
# Using pip
pip install deebase

# Using uv (recommended)
uv add deebase
```

DeeBase will automatically install its dependencies: SQLAlchemy, aiosqlite, asyncpg, and greenlet.

### Basic Example

```python
from deebase import Database
from datetime import datetime

# Connect to database
db = Database("sqlite+aiosqlite:///myapp.db")

# Define schema
class User:
    id: int
    name: str
    email: str
    created_at: datetime

# Create table
users = await db.create(User, pk='id')

# Insert
user = await users.insert({
    "name": "Alice",
    "email": "alice@example.com",
    "created_at": datetime.now()
})
# Returns: {'id': 1, 'name': 'Alice', 'email': 'alice@example.com', ...}

# Query
all_users = await users()  # All records
user = await users[1]       # By primary key
user = await users.lookup(email="alice@example.com")  # By column

# Update
user['name'] = "Alice Smith"
await users.update(user)

# Delete
await users.delete(1)

await db.close()
```

## Type Safety with Dataclasses

DeeBase supports two approaches for type-safe operations:

### Option 1: Start with a plain class, generate dataclass later

```python
# Create table from plain class
class User:
    id: int
    name: str
    email: str
    created_at: datetime

users = await db.create(User, pk='id')

# Later, enable dataclass mode for type-safe operations
UserDC = users.dataclass()

# Now all operations return dataclass instances
user = await users[1]
print(user.name)  # IDE autocomplete works!
print(user.email)

# Insert with dataclass
new_user = await users.insert(UserDC(
    id=None,
    name="Bob",
    email="bob@example.com",
    created_at=datetime.now()
))
```

### Option 2: Start with @dataclass (recommended for new code)

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class User:
    id: int
    name: str
    email: str
    created_at: datetime

# Create table - User is already a dataclass, no need for .dataclass()!
users = await db.create(User, pk='id')

# All operations automatically work with dataclass instances
user = await users[1]  # Returns User instance
print(user.name)       # IDE autocomplete works automatically!

# Insert with dataclass instance
new_user = await users.insert(User(
    id=None,  # Auto-generated
    name="Bob",
    email="bob@example.com",
    created_at=datetime.now()
))

# Mix dicts and dataclass instances as needed
await users.insert({"name": "Charlie", "email": "charlie@example.com", "created_at": datetime.now()})
```

## Rich Type System

```python
from deebase import Database, Text
from typing import Optional
from datetime import datetime

class Article:
    id: int
    title: str              # VARCHAR (limited)
    content: Text           # TEXT (unlimited)
    metadata: dict          # JSON column
    tags: Optional[list]    # JSON, nullable
    published: bool         # BOOLEAN
    view_count: int         # INTEGER
    created_at: datetime    # TIMESTAMP
    updated_at: Optional[datetime]  # TIMESTAMP, nullable

articles = await db.create(Article, pk='id')

article = await articles.insert({
    "title": "Getting Started",
    "content": "A very long article...",
    "metadata": {"author": "Alice", "category": "tutorial"},
    "tags": ["python", "async"],
    "published": True,
    "view_count": 0,
    "created_at": datetime.now()
})
```

## Error Handling

DeeBase provides specific exception types with rich context:

```python
from deebase import NotFoundError, IntegrityError, ValidationError

try:
    user = await users[999]
except NotFoundError as e:
    print(f"Not found in {e.table_name}")
    print(f"Filters: {e.filters}")

try:
    await users.insert({"email": "duplicate@example.com"})
except IntegrityError as e:
    print(f"Constraint {e.constraint} violated")

try:
    await users.update({"name": "Missing PK"})  # No ID
except ValidationError as e:
    print(f"Invalid {e.field}: {e.value}")
```

## Working with Existing Databases

```python
# Connect to existing database
db = Database("sqlite+aiosqlite:///existing.db")

# Reflect all tables
await db.reflect()

# Access tables
users = db.t.users
posts = db.t.posts

# CRUD operations work normally
user = await users[1]
all_posts = await posts()
```

## Database Views

```python
# Create view
popular_posts = await db.create_view(
    "popular_posts",
    "SELECT * FROM posts WHERE views > 1000"
)

# Query view (read-only)
posts = await popular_posts()

# Access via db.v
view = db.v.popular_posts
```

## Filtering with xtra()

```python
# Create filtered view of table
admin_users = users.xtra(role="admin")
active_admins = admin_users.xtra(active=True)

# All operations respect filters
admins = await active_admins()

# Insert automatically sets filter values
await active_admins.insert({"name": "Eve", "email": "eve@example.com"})
# Automatically sets role='admin' and active=True
```

## Code Generation

Export your database schema as Python dataclasses:

```python
from deebase import create_mod_from_tables

# Connect and reflect
db = Database("sqlite+aiosqlite:///myapp.db")
await db.reflect()

# Export all tables to models.py
create_mod_from_tables(
    "models.py",
    db.t.users,
    db.t.posts,
    db.t.comments,
    overwrite=True
)

# Now you can:
# from models import User, Post, Comment
```

## Examples

Runnable examples are available in the [`examples/`](examples/) folder:

- **[phase1_raw_sql.py](examples/phase1_raw_sql.py)** - Raw SQL queries
- **[phase2_table_creation.py](examples/phase2_table_creation.py)** - Creating tables from Python classes
- **[phase3_crud_operations.py](examples/phase3_crud_operations.py)** - Full CRUD operations
- **[phase4_dataclass_support.py](examples/phase4_dataclass_support.py)** - Type-safe operations with dataclasses
- **[phase5_reflection.py](examples/phase5_reflection.py)** - Working with existing databases
- **[phase7_views.py](examples/phase7_views.py)** - Database views
- **[phase8_polish_utilities.py](examples/phase8_polish_utilities.py)** - Error handling & code generation
- **[transactions.py](examples/transactions.py)** - Multi-operation atomic transactions
- **[complete_example.py](examples/complete_example.py)** - Full-featured blog database

Run any example:
```bash
uv run examples/complete_example.py
```

## Documentation

DeeBase documentation follows the [Divio documentation system](https://docs.divio.com/documentation-system/), providing four types of documentation for different needs:

```
                    DIVIO DOCUMENTATION SYSTEM

        Practical                    Theoretical
           │                              │
    ───────┼──────────────────────────────┼───────
           │                              │
    TUTORIALS (learning-oriented)  EXPLANATION (understanding-oriented)
           │                              │
    • examples/                    • how-it-works.md
      - phase1_raw_sql.py          • migrating_from_fastlite.md
      - phase2_table_creation.py   • implemented.md
      - phase3_crud_operations.py
      - phase4_dataclass_support.py
      - phase5_reflection.py
      - phase7_views.py
      - phase8_polish_utilities.py
      - complete_example.py
           │                              │
    ───────┼──────────────────────────────┼───────
           │                              │
    HOW-TO GUIDES (problem-oriented) REFERENCE (information-oriented)
           │                              │
    • best-practices.md            • api_reference.md
      - Dict vs Dataclass          • types_reference.md
      - Reflection decisions
      - Error handling patterns
      - Consistency strategies
           │                              │
```

### By Type

**📚 Tutorials** (Learning-oriented - "I want to learn")
- **[examples/](examples/)** - Hands-on runnable examples for each phase

**🔧 How-To Guides** (Problem-oriented - "I want to solve a problem")
- **[Best Practices](docs/best-practices.md)** - Design decisions and patterns (dict vs dataclass, reflection, consistency)

**📖 Reference** (Information-oriented - "I want to look up details")
- **[API Reference](docs/api_reference.md)** - Complete API documentation with "When to Use" guidance
- **[Type Reference](docs/types_reference.md)** - Type system mapping guide

**💡 Explanation** (Understanding-oriented - "I want to understand")
- **[How It Works](docs/how-it-works.md)** - Technical deep dive into internals
- **[Migration Guide](docs/migrating_from_fastlite.md)** - Understanding differences from fastlite
- **[Implementation Guide](docs/implemented.md)** - Feature guide showing what works

## Supported Databases

| Database | Status | Driver |
|----------|--------|--------|
| SQLite | ✅ Fully tested | aiosqlite |
| PostgreSQL | 🚧 Infrastructure ready | asyncpg |

## Supported Python Types

| Python Type | Database Type | Notes |
|-------------|---------------|-------|
| `int` | INTEGER | |
| `str` | VARCHAR | Limited length |
| `Text` | TEXT | Unlimited length |
| `float` | REAL/FLOAT | |
| `bool` | BOOLEAN | 0/1 in SQLite |
| `bytes` | BLOB/BYTEA | |
| `dict` | JSON | Auto-serialized in SQLite |
| `datetime` | TIMESTAMP | |
| `date` | DATE | |
| `time` | TIME | |
| `Optional[T]` | NULL-able | Any type can be nullable |

## Exception Types

| Exception | When Raised | Attributes |
|-----------|-------------|------------|
| `NotFoundError` | Record not found | `table_name`, `filters` |
| `IntegrityError` | Constraint violation | `constraint`, `table_name` |
| `ValidationError` | Invalid input | `field`, `value` |
| `SchemaError` | Schema error | `table_name`, `column_name` |
| `ConnectionError` | Connection failed | `database_url` |
| `InvalidOperationError` | Invalid operation | `operation`, `target` |

## FastAPI Integration

```python
from fastapi import FastAPI, Depends, HTTPException
from deebase import Database, NotFoundError

app = FastAPI()

def get_db():
    return Database("sqlite+aiosqlite:///myapp.db")

@app.get("/users")
async def list_users(db: Database = Depends(get_db)):
    users = db.t.users
    return await users()

@app.get("/users/{user_id}")
async def get_user(user_id: int, db: Database = Depends(get_db)):
    try:
        users = db.t.users
        return await users[user_id]
    except NotFoundError:
        raise HTTPException(status_code=404, detail="User not found")
```

## Comparison with fastlite

DeeBase replicates the fastlite API with async support:

| Feature | fastlite | DeeBase |
|---------|----------|---------|
| **Syntax** | Synchronous | Async (requires `await`) |
| **Backend** | sqlite-utils | SQLAlchemy |
| **Databases** | SQLite only | SQLite + PostgreSQL |
| **Type Safety** | Optional dataclasses | Optional dataclasses |
| **CRUD Operations** | Yes | Yes |
| **Views** | Yes | Yes |
| **Dynamic Access** | `db.t.tablename` | `db.t.tablename` (after reflection) |
| **Error Handling** | Basic | 6 specific exception types |
| **Code Generation** | No | Yes (`create_mod()`) |

See the [Migration Guide](docs/migrating_from_fastlite.md) for detailed comparison.

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/deebase --cov-report=html

# Run specific test file
uv run pytest tests/test_crud.py -v
```

All 161 tests passing ✅

### Project Structure

```
deebase/
├── src/deebase/
│   ├── __init__.py           # Public API
│   ├── database.py           # Database class
│   ├── table.py              # Table operations
│   ├── view.py               # View support
│   ├── column.py             # Column access
│   ├── types.py              # Type mapping
│   ├── dataclass_utils.py    # Dataclass utilities
│   └── exceptions.py         # Exception classes
├── tests/                     # 161 passing tests
├── examples/                  # Runnable examples
├── docs/                      # Documentation
└── README.md                  # This file
```

## Requirements

- Python 3.14+
- sqlalchemy 2.0.45+
- aiosqlite 0.22.0+
- greenlet 3.3.0+ (for SQLAlchemy async)

## Design Philosophy

DeeBase follows these principles:

1. **Start Simple** - Begin with dicts, opt-in to dataclasses for type safety
2. **Async First** - All operations are async for modern frameworks
3. **Database Agnostic** - Write once, run on SQLite or PostgreSQL
4. **No Magic** - Transparent SQLAlchemy usage with escape hatches
5. **Production Ready** - Comprehensive error handling and testing

## Status

**All 8 development phases complete! Ready for production use.**

- ✅ Phase 1: Core Infrastructure
- ✅ Phase 2: Table Creation & Schema
- ✅ Phase 3: CRUD Operations
- ✅ Phase 4: Dataclass Support
- ✅ Phase 5: Dynamic Access & Reflection
- ✅ Phase 6: xtra() Filtering
- ✅ Phase 7: Views Support
- ✅ Phase 8: Polish & Utilities

See [Implementation Plan](docs/implementation_plan.md) for details.

## Contributing

This project follows an 8-phase development plan (now complete). See [docs/implementation_plan.md](docs/implementation_plan.md) for the roadmap.

## License

TBD

## Acknowledgments

- Inspired by [fastlite](https://fastlite.answer.ai/) by Jeremy Howard
- Built on [SQLAlchemy](https://www.sqlalchemy.org/)
- Async support via [aiosqlite](https://github.com/omnilib/aiosqlite)

---

**Made with ❤️ for the async Python community**
