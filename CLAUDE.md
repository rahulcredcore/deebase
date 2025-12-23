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
🚧 **Phase 2 In Progress** - Table Creation & Schema

**Completed:**
- Database class with async engine and `q()` method
- Enhanced type system (Text, JSON, all basic types)
- Complete dataclass utilities
- 62 passing tests

**Current Focus:** Implementing `db.create()` for table creation from Python classes

See [docs/implementation_plan.md](docs/implementation_plan.md) for detailed implementation roadmap.

## Basic Usage

### Working Now (Phase 1)

```python
from deebase import Database

# Create database connection
db = Database("sqlite+aiosqlite:///myapp.db")

# Raw SQL queries (fully working)
await db.q("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
await db.q("INSERT INTO users (name) VALUES ('Alice')")
results = await db.q("SELECT * FROM users")
# Returns: [{'id': 1, 'name': 'Alice'}]

# Access underlying SQLAlchemy engine
engine = db.engine
```

### Coming in Phase 2

```python
from deebase import Database, Text
from datetime import datetime

# Define a table structure with rich types
class Article:
    id: int
    title: str              # VARCHAR (short string)
    slug: str               # VARCHAR
    content: Text           # TEXT (unlimited)
    metadata: dict          # JSON column
    created_at: datetime    # TIMESTAMP

# Create table from class
articles = await db.create(Article, pk='id')

# Insert records (returns dict by default)
article = await articles.insert({
    "title": "Getting Started",
    "slug": "getting-started",
    "content": "Long article content...",
    "metadata": {"author": "Alice", "tags": ["tutorial"]},
    "created_at": datetime.now()
})

# Query records
all_articles = await articles()
article = await articles[1]
found = await articles.lookup(slug="getting-started")

# Enable dataclass mode for type safety
Article = articles.dataclass()
typed_article = await articles.insert(Article(...))
# typed_article is now an Article dataclass instance

# Update and delete
await articles.update(Article(id=1, title="Updated Title", ...))
await articles.delete(1)

# Access underlying SQLAlchemy
sa_table = articles.sa_table
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

**Phase 2: Table Creation & Schema** 🚧 IN PROGRESS
- [ ] `db.create()` implementation
- [ ] Table schema property
- [ ] Tests for table creation

**Phase 3+:** CRUD operations, dataclass support, filtering, views, polish

See [docs/implementation_plan.md](docs/implementation_plan.md) for complete 8-phase roadmap.

## Contributing

This project is in early development. The implementation follows an 8-phase plan documented in `docs/implementation_plan.md`.

## License

TBD
