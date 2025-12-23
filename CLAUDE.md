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

✅ **Phase 1 Complete** - Core Infrastructure with enhancements
✅ **Phase 2 Complete** - Table Creation & Schema
✅ **Phase 3 Complete** - CRUD Operations
✅ **Phase 4 Complete** - Dataclass Support
🚧 **Phase 5 In Progress** - Dynamic Access & Reflection

**Completed:**
- Database class with async engine and `q()` method
- Enhanced type system (Text, JSON, all basic types)
- Complete dataclass utilities
- Table creation from Python classes with `db.create()`
- Schema inspection and table dropping
- Full CRUD operations (insert, update, upsert, delete, select, lookup)
- Composite primary keys
- xtra() filtering
- Error handling with NotFoundError
- Dataclass support (`.dataclass()`, `@dataclass`, type-safe operations)
- 125 passing tests (105 + 20 new)

**Current Focus:** Next phase will add dynamic table access and reflection (db.t.users)

See [docs/implementation_plan.md](docs/implementation_plan.md) for detailed implementation roadmap.
See [docs/implemented.md](docs/implemented.md) for comprehensive usage examples of implemented features.

## Basic Usage

### Working Now (Phases 1-4)

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

# View schema
print(articles.schema)

# Access underlying SQLAlchemy
engine = db.engine
sa_table = articles.sa_table

# Drop table
await articles.drop()
```

### Coming in Phase 5+

```python
# Phase 5: Dynamic Access & Reflection
# Access existing tables without defining classes
users = db.t.users              # Reflect from database
posts = db.t['posts']           # Alternative syntax
users, posts = db.t['users', 'posts']  # Multiple tables

# Phase 7: Views
view = await db.create_view(
    "popular_posts",
    "SELECT * FROM posts WHERE views > 1000"
)
popular = await view()  # Read-only access
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
- **Lazy reflection** - Tables reflected from database on first access
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

**Phase 5+:** Dynamic access & reflection, views, polish

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

# Complete example: Blog database with full features
uv run examples/complete_example.py
```

All examples use in-memory databases and demonstrate:
- Database connection and setup
- Raw SQL execution
- Table creation with rich types (str, Text, dict/JSON)
- Full CRUD operations (insert, update, upsert, delete, select, lookup)
- Dataclass support for type-safe operations
- Composite primary keys
- xtra() filtering
- Error handling
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
