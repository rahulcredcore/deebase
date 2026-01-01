# DeeBase

Async SQLAlchemy-based implementation of the fastlite API.

## Overview

DeeBase is an async database library that provides an ergonomic, interactive interface for SQLite and PostgreSQL databases. It replicates the [fastlite](https://fastlite.answer.ai/) API using SQLAlchemy as the backend, designed specifically for async Python environments like FastAPI.

## Key Features

- **Async/await support** - Built on SQLAlchemy's async engine for modern Python applications
- **Ergonomic API** - Simple, intuitive database operations inspired by fastlite
- **Opt-in type safety** - Work with dicts for quick scripting or dataclasses for type safety
- **Multiple backends** - Support for SQLite (via aiosqlite) and PostgreSQL (via asyncpg)
- **Rich type system** - Text (unlimited) vs String (limited), JSON columns, datetime support
- **Dynamic table access** - Access tables with `db.t.users` or `db.t['users']`
- **SQLAlchemy escape hatch** - Full access to underlying SQLAlchemy objects when needed

## Design Philosophy

DeeBase follows fastlite's philosophy of providing a simple, interactive database interface while adding async support. Key design principles:

1. **Start simple, add complexity when needed** - Begin with dict-based operations, opt-in to dataclasses
2. **Database-agnostic** - Write once, run on SQLite or PostgreSQL
3. **Async-first** - All database operations are async for modern web frameworks
4. **No magic** - Transparent SQLAlchemy usage with escape hatches for advanced features

## Project Status

✅ **Phases 1-10 Complete** - Production-ready with FK support

✅ **Phase 1 Complete** - Core Infrastructure with enhancements
✅ **Phase 2 Complete** - Table Creation & Schema
✅ **Phase 3 Complete** - CRUD Operations (includes xtra() from Phase 6, with_pk from Phase 7)
✅ **Phase 4 Complete** - Dataclass Support
✅ **Phase 5 Complete** - Dynamic Access & Reflection
✅ **Phase 6 Complete** - xtra() Filtering (implemented early in Phase 3)
✅ **Phase 7 Complete** - Views Support
✅ **Phase 8 Complete** - Polish & Utilities
✅ **Phase 9 Complete** - Transaction Support
✅ **Phase 10 Complete** - Foreign Keys & Defaults

**Completed Features:**
- ✅ Database class with async engine and `q()` method
- ✅ Enhanced type system (Text, JSON, ForeignKey, all basic types)
- ✅ Complete dataclass utilities
- ✅ Table creation from Python classes with `db.create()`
- ✅ Foreign key support via `ForeignKey[T, "table"]` type annotation
- ✅ Automatic default value extraction from class definitions
- ✅ Schema inspection and table dropping
- ✅ Full CRUD operations (insert, update, upsert, delete, select, lookup)
- ✅ Composite primary keys
- ✅ xtra() filtering
- ✅ Comprehensive error handling (6 specific exception types with rich context)
- ✅ Dataclass support (`.dataclass()`, `@dataclass`, type-safe operations)
- ✅ Table reflection (`db.reflect()`, `db.reflect_table()`)
- ✅ Dynamic table access (`db.t.tablename`, `db.t['table1', 'table2']`)
- ✅ Views support (`db.create_view()`, `db.v.viewname`, read-only operations)
- ✅ Code generation (`dataclass_src()`, `create_mod()`, `create_mod_from_tables()`)
- ✅ Transaction support (`db.transaction()`, atomic multi-operation commits)
- ✅ Complete documentation (API reference, migration guide, examples)
- ✅ 219 passing tests

**Phase 8 Deliverables:**
- 6 new exception types: `DeeBaseError`, `NotFoundError`, `IntegrityError`, `ValidationError`, `SchemaError`, `ConnectionError`, `InvalidOperationError`
- 3 code generation utilities: `dataclass_src()`, `create_mod()`, `create_mod_from_tables()`
- 2 comprehensive documentation files: API reference, migration guide from fastlite
- Comprehensive Phase 8 example file demonstrating all error handling and code generation features
- Enhanced error messages throughout with rich context

**Phase 9 Deliverables:**
- Transaction context manager: `db.transaction()` for atomic multi-operation commits
- Automatic commit on success, rollback on any exception
- Thread-safe implementation using Python's contextvars
- All CRUD operations automatically participate in active transactions
- 22 new transaction tests (183 total passing tests)
- Comprehensive transactions.py example with 8 real-world scenarios
- Zero breaking changes - fully backward compatible

**Phase 10 Deliverables:**
- `ForeignKey[T, "table.column"]` type annotation for foreign key columns
- Automatic extraction of scalar defaults from class definitions
- `if_not_exists` parameter for CREATE TABLE IF NOT EXISTS
- `replace` parameter to drop and recreate tables
- Uses Python's native features (Optional for nullable, class defaults for SQL defaults)
- Input flexibility: accepts both regular classes (→ dict rows) and dataclasses (→ dataclass rows)
- 36 new tests (219 total passing tests)

See [docs/implementation_plan.md](docs/implementation_plan.md) for detailed implementation roadmap.
See [docs/implemented.md](docs/implemented.md) for comprehensive usage examples of implemented features.

## Basic Usage

### Working Now (Phases 1-10)

```python
from deebase import Database, Text, NotFoundError
from datetime import datetime

# Create database connection
db = Database("sqlite+aiosqlite:///myapp.db")

# Raw SQL queries (Phase 1)
await db.q("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
await db.q("INSERT INTO users (name) VALUES ('Alice')")
results = await db.q("SELECT * FROM users")
# Returns: [{'id': 1, 'name': 'Alice'}]

# Create tables from Python classes (Phase 2)
class Article:
    id: int
    title: str              # VARCHAR
    content: Text           # TEXT (unlimited)
    metadata: dict          # JSON column
    created_at: datetime    # TIMESTAMP

articles = await db.create(Article, pk='id')

# CRUD Operations (Phase 3)

# INSERT
article = await articles.insert({
    "title": "Getting Started",
    "content": "Long article content...",
    "metadata": {"author": "Alice", "tags": ["tutorial"]},
    "created_at": datetime.now()
})
# Returns: {'id': 1, 'title': 'Getting Started', ...}

# SELECT all
all_articles = await articles()
# Returns: [{'id': 1, ...}, {'id': 2, ...}]

# SELECT with limit
recent = await articles(limit=5)

# GET by primary key
article = await articles[1]

# LOOKUP by column
found = await articles.lookup(title="Getting Started")

# UPDATE
article['metadata']['views'] = 100
updated = await articles.update(article)

# UPSERT (insert or update)
await articles.upsert({"id": 1, "title": "Updated Title", ...})

# DELETE
await articles.delete(1)

# Error handling
try:
    await articles[999]
except NotFoundError:
    print("Article not found")

# xtra() filtering
user_articles = articles.xtra(author_id=1)
my_articles = await user_articles()  # Only author_id=1

# Dataclass support (Phase 4)
ArticleDC = articles.dataclass()  # Generate dataclass from table

# Insert with dataclass instance
new_article = await articles.insert(ArticleDC(
    id=None,
    title="Another Article",
    content="More content...",
    metadata={"author": "Bob"},
    created_at=datetime.now()
))
# new_article is an ArticleDC instance - type-safe field access!
print(new_article.title)  # IDE autocomplete works

# All operations return dataclass instances
all_articles = await articles()
for a in all_articles:
    print(a.title)  # Field access, not dict['key']

# Reflection and dynamic access (Phase 5)

# Reflect existing tables from database
await db.reflect()

# Dynamic table access (sync, fast cache lookups)
users = db.t.users
posts = db.t.posts

# Multiple tables at once
users, posts, comments = db.t['users', 'posts', 'comments']

# Tables created with raw SQL + reflection
await db.q("CREATE TABLE products (id INT PRIMARY KEY, name TEXT)")
await db.reflect_table('products')  # Reflect single table
products = db.t.products  # Now works

# View schema
print(articles.schema)

# Access underlying SQLAlchemy
engine = db.engine
sa_table = articles.sa_table

# Drop table
await articles.drop()

# Views support (Phase 7)

# Create view from SELECT query
view = await db.create_view(
    "popular_posts",
    "SELECT * FROM posts WHERE views > 1000"
)
popular = await view()  # Read-only access

# Dynamic view access (sync, fast cache lookups)
view = db.v.popular_posts

# Views support all read operations
post = await view[1]
found = await view.lookup(title="...")
limited = await view(limit=10)

# Dataclass support for views
PostViewDC = view.dataclass()
results = await view()  # Returns dataclass instances

# Transaction support (Phase 9)

# Multi-operation atomic transactions
async with db.transaction():
    await users.insert({"name": "Alice", "balance": 100})
    await users.insert({"name": "Bob", "balance": 50})
    # Both commit atomically, or both rollback on error

# Money transfer with automatic rollback
async with db.transaction():
    alice = await users.lookup(name="Alice")
    bob = await users.lookup(name="Bob")
    alice['balance'] -= 30
    bob['balance'] += 30
    await users.update(alice)
    await users.update(bob)
    # If any operation fails, all changes roll back

# Automatic rollback on exception
try:
    async with db.transaction():
        await users.insert({"name": "Charlie", "balance": 200})
        raise ValueError("Oops!")  # All changes rolled back
except ValueError:
    pass

# Backward compatible - operations without transactions still auto-commit
await users.insert({"name": "Diana", "balance": 150})  # Auto-commits

# Foreign Keys & Defaults (Phase 10)

from deebase import ForeignKey

# Define tables with FK relationships and defaults
class User:
    id: int
    name: str
    email: str
    status: str = "active"  # SQL DEFAULT 'active'

class Post:
    id: int
    author_id: ForeignKey[int, "user"]  # FK to user.id
    title: str
    views: int = 0  # SQL DEFAULT 0

users = await db.create(User, pk='id', if_not_exists=True)
posts = await db.create(Post, pk='id', if_not_exists=True)

# Enable FK enforcement in SQLite
await db.q("PRAGMA foreign_keys = ON")

# Insert user (status defaults to "active")
user = await users.insert({"name": "Alice", "email": "alice@example.com"})

# Insert post with FK (views defaults to 0)
post = await posts.insert({
    "author_id": user["id"],
    "title": "Hello World"
})

# FK constraint enforced by database
try:
    await posts.insert({"author_id": 999, "title": "Invalid"})  # FK violation
except IntegrityError:
    print("Author does not exist")
```

## Architecture

```
src/deebase/
├── __init__.py           # Public API exports
├── database.py           # Database class with async engine
├── table.py              # Table class wrapping SQLAlchemy tables
├── column.py             # Column accessor and wrapper
├── view.py               # View support (read-only tables)
├── types.py              # Python → SQLAlchemy type mapping
├── dataclass_utils.py    # Dataclass generation and handling
└── exceptions.py         # Custom exceptions (NotFoundError, etc.)
```

## Implementation Approach

- **Pure SQLAlchemy Core** - No ORM, just Core APIs for simplicity and control
- **Async session per operation** - Each operation creates a short-lived async session
- **Metadata caching** - Table metadata cached and reused
- **Explicit reflection** - Tables reflected from database with `db.reflect()` or `db.reflect_table()`
- **Context-dependent returns** - Methods return dicts or dataclasses based on configuration

## Differences from fastlite

1. **Async everywhere** - All methods are async (`await table.insert(...)`)
2. **SQLAlchemy backend** - Uses SQLAlchemy instead of sqlite-utils
3. **Multi-database** - Supports both SQLite and PostgreSQL
4. **Explicit connections** - Connection string required (no default file)

## Development Status

**Phase 1: Core Infrastructure** ✅ COMPLETE
- ✅ Database class with async engine
- ✅ `q()` method for raw SQL (handles SELECT and DDL/DML)
- ✅ Enhanced type mapping system (Text, JSON, all basic types)
- ✅ Complete dataclass utilities
- ✅ Test infrastructure (62 passing tests)

**Phase 2: Table Creation & Schema** ✅ COMPLETE
- ✅ `db.create()` implementation
- ✅ Table schema property
- ✅ Table.drop() method
- ✅ 16 new tests (78 total passing)

**Phase 3: CRUD Operations** ✅ COMPLETE
- ✅ `table.insert()` - Insert records with auto-generated PKs
- ✅ `table.update()` - Update records
- ✅ `table.upsert()` - Insert or update
- ✅ `table.delete()` - Delete records
- ✅ `table()` - Select all/limited records
- ✅ `table[pk]` - Get by primary key
- ✅ `table.lookup()` - Query with WHERE conditions
- ✅ Composite primary keys
- ✅ xtra() filtering
- ✅ Error handling with NotFoundError
- ✅ 27 new tests (105 total passing)

**Phase 4: Dataclass Support** ✅ COMPLETE
- ✅ `table.dataclass()` - Generate dataclass from table metadata
- ✅ CRUD operations with dataclass instances
- ✅ Support for actual `@dataclass` decorated classes
- ✅ Mix dict and dataclass inputs seamlessly
- ✅ Type-safe operations with IDE autocomplete
- ✅ 20 new tests (125 total passing)

**Phase 5: Dynamic Access & Reflection** ✅ COMPLETE
- ✅ `db.reflect()` - Reflect all tables from database
- ✅ `db.reflect_table(name)` - Reflect single table
- ✅ `db.t.tablename` - Dynamic table access (cache-only, sync)
- ✅ `db.t['table1', 'table2']` - Multiple table access
- ✅ Auto-caching from `db.create()`
- ✅ Full CRUD on reflected tables
- ✅ 16 new tests (142 total passing)

**Phase 6: xtra() Filtering** ✅ COMPLETE (Implemented in Phase 3)
- ✅ All items completed in Phase 3

**Phase 7: Views Support** ✅ COMPLETE
- ✅ `db.create_view(name, sql, replace)` - Create database views
- ✅ `db.reflect_view(name)` - Reflect existing views
- ✅ `db.v.viewname` - Dynamic view access (cache-only, sync)
- ✅ Read-only operations (SELECT, GET, LOOKUP)
- ✅ Write operations blocked (INSERT, UPDATE, DELETE)
- ✅ View.drop() - Drop views
- ✅ Dataclass support for views
- ✅ 19 new tests (161 total passing)

**Phase 8: Polish & Utilities** ✅ COMPLETE
- ✅ 6 new exception types with rich context
- ✅ Code generation utilities (dataclass_src, create_mod, create_mod_from_tables)
- ✅ Complete API reference documentation
- ✅ Migration guide from fastlite
- ✅ Production-ready error handling

**Phase 9: Transaction Support** ✅ COMPLETE
- ✅ `db.transaction()` context manager for atomic operations
- ✅ Automatic commit on success, rollback on exception
- ✅ Thread-safe implementation using contextvars
- ✅ All CRUD operations automatically participate
- ✅ 22 new tests (183 total passing)
- ✅ Zero breaking changes, fully backward compatible

**Phase 10: Foreign Keys & Defaults** ✅ COMPLETE
- ✅ `ForeignKey[T, "table"]` type annotation for FK relationships
- ✅ `ForeignKey[T, "table.column"]` for explicit column references
- ✅ Automatic extraction of scalar defaults from class definitions
- ✅ `if_not_exists` parameter for safe table creation
- ✅ `replace` parameter to drop and recreate tables
- ✅ 36 new tests (219 total passing)

See [docs/implementation_plan.md](docs/implementation_plan.md) for complete 10-phase roadmap.
See [docs/implemented.md](docs/implemented.md) for detailed usage examples of all working features.

## Examples

Runnable examples are available in the `examples/` folder:

```bash
# Phase 1: Raw SQL queries
uv run examples/phase1_raw_sql.py

# Phase 2: Table creation from Python classes
uv run examples/phase2_table_creation.py

# Phase 3: CRUD operations
uv run examples/phase3_crud_operations.py

# Phase 4: Dataclass support
uv run examples/phase4_dataclass_support.py

# Phase 5: Reflection and dynamic access
uv run examples/phase5_reflection.py

# Phase 7: Views support
uv run examples/phase7_views.py

# Phase 8: Production polish and utilities
uv run examples/phase8_polish_utilities.py

# Phase 9: Transaction support
uv run examples/phase9_transactions.py

# Phase 10: Foreign keys and defaults
uv run examples/phase10_foreign_keys_defaults.py

# Complete example: Blog database with full features
uv run examples/complete_example.py
```

All examples use in-memory databases and demonstrate:
- Database connection and setup
- Raw SQL execution
- Table creation with rich types (str, Text, dict/JSON, ForeignKey)
- Full CRUD operations (insert, update, upsert, delete, select, lookup)
- Foreign key relationships via `ForeignKey[T, "table"]` type annotation
- Default values from class definitions (SQL DEFAULT)
- Dataclass support for type-safe operations
- Table reflection and dynamic access (db.t.tablename)
- Composite primary keys
- xtra() filtering
- Comprehensive error handling with rich exception context
- Code generation utilities (dataclass_src, create_mod, create_mod_from_tables)
- Transaction support for atomic multi-operation commits
- Production-ready error handling patterns
- Schema inspection
- Practical usage patterns

See [examples/README.md](examples/README.md) for details.

## Documentation

DeeBase documentation follows the [Divio documentation system](https://docs.divio.com/documentation-system/):

```
                    DIVIO DOCUMENTATION SYSTEM

        Practical                    Theoretical
           │                              │
    ───────┼──────────────────────────────┼───────
           │                              │
    TUTORIALS (learning-oriented)  EXPLANATION (understanding-oriented)
           │                              │
    • examples/                    • how-it-works.md
      (runnable phase examples     • migrating_from_fastlite.md
       + complete_example.py)      • implemented.md
           │                              │
    ───────┼──────────────────────────────┼───────
           │                              │
    HOW-TO GUIDES (problem-oriented) REFERENCE (information-oriented)
           │                              │
    • best-practices.md            • api_reference.md
      - Dict vs Dataclass          • types_reference.md
      - Reflection decisions       • implementation_plan.md
      - Error handling patterns
           │                              │
```

**Full Documentation:**
- **[docs/api_reference.md](docs/api_reference.md)** - Complete API documentation with "When to Use" guidance
- **[docs/best-practices.md](docs/best-practices.md)** - Design decisions and patterns (dict vs dataclass, reflection, consistency)
- **[docs/implemented.md](docs/implemented.md)** - User guide showing what works at each phase
- **[docs/migrating_from_fastlite.md](docs/migrating_from_fastlite.md)** - Migration guide from fastlite
- **[docs/how-it-works.md](docs/how-it-works.md)** - Technical guide explaining SQLAlchemy internals
- **[docs/types_reference.md](docs/types_reference.md)** - Complete type system reference
- **[docs/implementation_plan.md](docs/implementation_plan.md)** - 10-phase development roadmap
- **[examples/](examples/)** - Runnable code examples

## Development Workflow

When implementing a new phase, follow this workflow:

### 1. Planning
- Extract phase plans from `docs/phase11_12_future.md` (or create new)
- Get user approval on the plan
- Add approved plan to `docs/implementation_plan.md`

### 2. Implementation
- Implement the feature in relevant source files
- Write tests in `tests/`

### 3. Testing
- Run `uv run pytest` - ensure all tests pass
- Run all examples to verify no regressions

### 4. Documentation Updates (one by one)
Update each documentation file:
1. `examples/phaseN_*.py` - Create phase example
2. `examples/complete_example.py` - Add new feature showcase
3. `docs/api_reference.md` - API documentation
4. `docs/implemented.md` - Feature guide
5. `docs/best-practices.md` - Design decisions
6. `docs/types_reference.md` - If new types added
7. `docs/how-it-works.md` - SQLAlchemy implementation details
8. `README.md` - User-facing documentation
9. `CLAUDE.md` - Developer context

### 5. Finalize
- Run all tests and examples one final time
- `git add && git commit && git push`

### Future Phases
See `docs/phase11_12_future.md` for planned features:
- Phase 11: FK Navigation (relationship loading)
- Phase 12: Indexes, FTS, Joins

## Contributing

This project is production-ready. The implementation follows a 10-phase plan documented in `docs/implementation_plan.md`.

## License

TBD
