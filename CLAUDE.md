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

✅ **ALL 8 PHASES COMPLETE! READY FOR PRODUCTION!** 🎉

✅ **Phase 1 Complete** - Core Infrastructure with enhancements
✅ **Phase 2 Complete** - Table Creation & Schema
✅ **Phase 3 Complete** - CRUD Operations (includes xtra() from Phase 6, with_pk from Phase 7)
✅ **Phase 4 Complete** - Dataclass Support
✅ **Phase 5 Complete** - Dynamic Access & Reflection
✅ **Phase 6 Complete** - xtra() Filtering (implemented early in Phase 3)
✅ **Phase 7 Complete** - Views Support
✅ **Phase 8 Complete** - Polish & Utilities

**Completed Features:**
- ✅ Database class with async engine and `q()` method
- ✅ Enhanced type system (Text, JSON, all basic types)
- ✅ Complete dataclass utilities
- ✅ Table creation from Python classes with `db.create()`
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
- ✅ Complete documentation (API reference, migration guide, examples)
- ✅ 161 passing tests

**Phase 8 Deliverables:**
- 6 new exception types: `DeeBaseError`, `NotFoundError`, `IntegrityError`, `ValidationError`, `SchemaError`, `ConnectionError`, `InvalidOperationError`
- 3 code generation utilities: `dataclass_src()`, `create_mod()`, `create_mod_from_tables()`
- 2 comprehensive documentation files: API reference, migration guide from fastlite
- Comprehensive Phase 8 example file demonstrating all error handling and code generation features
- Enhanced error messages throughout with rich context

See [docs/implementation_plan.md](docs/implementation_plan.md) for detailed implementation roadmap.
See [docs/implemented.md](docs/implemented.md) for comprehensive usage examples of implemented features.

## Basic Usage

### Working Now (Phases 1-7)

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

**Phase 8:** Polish & utilities (final phase)

See [docs/implementation_plan.md](docs/implementation_plan.md) for complete 8-phase roadmap.
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

# Complete example: Blog database with full features
uv run examples/complete_example.py
```

All examples use in-memory databases and demonstrate:
- Database connection and setup
- Raw SQL execution
- Table creation with rich types (str, Text, dict/JSON)
- Full CRUD operations (insert, update, upsert, delete, select, lookup)
- Dataclass support for type-safe operations
- Table reflection and dynamic access (db.t.tablename)
- Composite primary keys
- xtra() filtering
- Comprehensive error handling with rich exception context
- Code generation utilities (dataclass_src, create_mod, create_mod_from_tables)
- Production-ready error handling patterns
- Schema inspection
- Practical usage patterns

See [examples/README.md](examples/README.md) for details.

## Documentation

DeeBase includes comprehensive documentation:

- **[docs/implemented.md](docs/implemented.md)** - User guide showing what works at each phase
- **[docs/how-it-works.md](docs/how-it-works.md)** - Technical guide explaining SQLAlchemy internals
- **[docs/types_reference.md](docs/types_reference.md)** - Complete type system reference
- **[docs/implementation_plan.md](docs/implementation_plan.md)** - 8-phase development roadmap
- **[examples/](examples/)** - Runnable code examples

## Contributing

This project is in early development. The implementation follows an 8-phase plan documented in `docs/implementation_plan.md`.

## License

TBD
