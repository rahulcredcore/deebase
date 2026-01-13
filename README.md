# DeeBase

**Async SQLAlchemy-based database library with an ergonomic, fastlite-inspired API**

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![SQLAlchemy 2.0+](https://img.shields.io/badge/sqlalchemy-2.0+-green.svg)](https://www.sqlalchemy.org/)
[![Tests](https://img.shields.io/badge/tests-539%20passing-brightgreen.svg)](#)
[![License](https://img.shields.io/badge/license-TBD-lightgrey.svg)](#)

DeeBase provides a simple, intuitive interface for async database operations in Python. Built on SQLAlchemy, it combines the ergonomics of [fastlite](https://fastlite.answer.ai/) with full async/await support and multi-database compatibility.

## Features

- **🚀 Async/Await** - Built for modern async Python (FastAPI, etc.)
- **📝 Ergonomic API** - Simple, intuitive database operations
- **🔒 Type Safety** - Optional dataclass support with IDE autocomplete
- **🎯 Multi-Database** - SQLite and PostgreSQL support
- **🛠️ Rich Types** - Text, JSON, ForeignKey, datetime, Optional support
- **🔗 Foreign Keys** - ForeignKey type annotation for relationships
- **🧭 FK Navigation** - Navigate FK relationships with `table.fk.column(record)`
- **⚙️ Default Values** - Automatic SQL defaults from class definitions
- **⚡ Dynamic Access** - Access tables with `db.t.tablename`
- **🔍 Views Support** - Read-only database views
- **💾 Transactions** - Atomic multi-operation commits with rollback
- **🎨 Error Handling** - 6 specific exception types with rich context
- **📤 Code Generation** - Export schemas as Python dataclasses
- **📊 Indexes** - Query optimization with named and unique indexes
- **🖥️ CLI** - Command-line interface for project management
- **🔄 Migrations** - Database schema migrations with up/down support
- **🌐 FastAPI Integration** - Auto-generated CRUD routers with FK validation
- **✅ Validation** - Shared validation layer for CLI, admin, and API
- **🔧 Admin Interface** - Django-like admin UI at `/admin/`

### Auto-Generated REST API

Define your models, get a full CRUD API with Swagger documentation:

![Auto-generated Swagger UI](docs/swagger-crud-endpoints.png)

### Django-like Admin Interface

Manage your data through a built-in admin UI at `/admin/`:

![Admin Dashboard](docs/admin-dashboard.png)

![Admin List View](docs/admin-list-view.png)

## Quick Start

### Installation

```bash
# Using pip
pip install deebase

# Using uv (recommended)
uv add deebase

# With FastAPI integration (optional)
pip install "deebase[api]"
# or: uv add "deebase[api]"

# Install globally as a CLI tool
uvx tool install deebase
```

DeeBase will automatically install its dependencies: SQLAlchemy, aiosqlite, asyncpg, and greenlet.

The `[api]` extra installs FastAPI integration dependencies: fastapi, pydantic, fastcore, uvicorn, and jinja2.

**Running the CLI:**
```bash
# If installed as a dependency in your project
uv run deebase --help

# If installed globally with uvx
deebase --help
```

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
    • examples/README.md           • migrating_from_fastlite.md
                                   • implemented.md
           │                              │
    ───────┼──────────────────────────────┼───────
           │                              │
    HOW-TO GUIDES (problem-oriented) REFERENCE (information-oriented)
           │                              │
    • best-practices.md            • api_reference.md
    • fastapi_guide.md             • cli_reference.md
                                   • types_reference.md
                                   • implementation_plan.md
           │                              │
```

### By Type

**📚 Tutorials** (Learning-oriented - "I want to learn")
- **[examples/](examples/)** - Hands-on runnable examples for each phase
- **[examples/README.md](examples/README.md)** - Example index with descriptions and running instructions

**🔧 How-To Guides** (Problem-oriented - "I want to solve a problem")
- **[Best Practices](docs/best-practices.md)** - Design decisions and patterns (dict vs dataclass, reflection, consistency)
- **[FastAPI Guide](docs/fastapi_guide.md)** - Building REST APIs with CRUD routers, hooks, and FK validation

**📖 Reference** (Information-oriented - "I want to look up details")
- **[API Reference](docs/api_reference.md)** - Complete API documentation with "When to Use" guidance
- **[CLI Reference](docs/cli_reference.md)** - All CLI commands with examples
- **[Type Reference](docs/types_reference.md)** - Type system mapping guide
- **[Implementation Plan](docs/implementation_plan.md)** - Development roadmap and phase details

**💡 Explanation** (Understanding-oriented - "I want to understand")
- **[How It Works](docs/how-it-works.md)** - Technical deep dive into internals
- **[Migration Guide](docs/migrating_from_fastlite.md)** - Understanding differences from fastlite
- **[Implementation Guide](docs/implemented.md)** - Feature guide showing what works

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

## Foreign Keys and Defaults

```python
from deebase import Database, ForeignKey, Text

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
    content: Text
    views: int = 0  # SQL DEFAULT 0

db = Database("sqlite+aiosqlite:///app.db")
users = await db.create(User, pk='id', if_not_exists=True)
posts = await db.create(Post, pk='id', if_not_exists=True)

# Enable FK enforcement in SQLite
await db.q("PRAGMA foreign_keys = ON")

# Insert parent first
user = await users.insert({"name": "Alice", "email": "alice@example.com"})
# status defaults to "active"

# Insert child with FK
post = await posts.insert({
    "author_id": user["id"],
    "title": "Hello World",
    "content": "My first post..."
})
# views defaults to 0
```

## FK Navigation

Navigate foreign key relationships to fetch related records:

```python
# Convenience API - clean syntax for FK navigation
author = await posts.fk.author_id(post)  # Get the author of this post
print(author["name"])  # "Alice"

# Power User API - explicit method calls
author = await posts.get_parent(post, "author_id")

# Get all children via FK
posts_by_user = await users.get_children(user, "post", "author_id")
for p in posts_by_user:
    print(p["title"])

# Access FK metadata
print(posts.foreign_keys)
# [{'column': 'author_id', 'references': 'user.id'}]

# Safe navigation - returns None for null FKs or dangling references
draft = await posts.insert({"author_id": None, "title": "Draft"})
author = await posts.fk.author_id(draft)  # Returns None
```

## Indexes

Create indexes to optimize query performance:

```python
from deebase import Database, Index

class Article:
    id: int
    title: str
    slug: str
    author_id: int
    created_at: str

# Create table with indexes
articles = await db.create(
    Article,
    pk='id',
    indexes=[
        "slug",                                    # Simple index (auto-named)
        ("author_id", "created_at"),               # Composite index
        Index("idx_title", "title", unique=True),  # Named unique index
    ]
)

# Add indexes after table creation
await articles.create_index("author_id")
await articles.create_index(["author_id", "created_at"], name="idx_author_date")
await articles.create_index("slug", unique=True)

# List indexes
for idx in articles.indexes:
    print(f"{idx['name']}: {idx['columns']} (unique={idx['unique']})")

# Drop index
await articles.drop_index("idx_author_date")
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

Views are the recommended way to handle JOIN queries in DeeBase:

```python
# Create view with JOIN
post_details = await db.create_view(
    "post_details",
    """
    SELECT p.id, p.title, u.name as author_name
    FROM posts p JOIN users u ON p.author_id = u.id
    """
)

# Query view - full DeeBase API works!
posts = await post_details()              # All rows
posts = await post_details(limit=10)      # With limit
post = await post_details.lookup(author_name="Alice")

# Generate dataclass for type-safe access
PostDetailDC = post_details.dataclass()
for post in await post_details():
    print(f"{post.title} by {post.author_name}")

# Access via db.v
view = db.v.post_details
```

Views let you handle JOINs without needing a Python class - the database provides column metadata. See [Best Practices](docs/best-practices.md#using-views-for-joins-and-ctes) for patterns.

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

## FastAPI Integration

Build REST APIs quickly with auto-generated CRUD routers:

```bash
# Install API dependencies
pip install "deebase[api]"
# or: uv add "deebase[api]"
```

```python
from dataclasses import dataclass
from fastapi import FastAPI
from deebase import Database, ForeignKey
from deebase.api import create_crud_router

@dataclass
class User:
    id: int
    name: str
    email: str

@dataclass
class Post:
    id: int
    author_id: ForeignKey[int, "user"]
    title: str
    content: str

app = FastAPI()
db = Database("sqlite+aiosqlite:///blog.db")

# Auto-generate CRUD endpoints
app.include_router(create_crud_router(
    db=db,
    model_cls=User,
    prefix="/api/users",
    tags=["Users"],
))

# With FK validation (validates author_id exists before insert)
app.include_router(create_crud_router(
    db=db,
    model_cls=Post,
    prefix="/api/posts",
    tags=["Posts"],
    validate_fks=True,
))

# Generated endpoints:
# GET    /api/users/      - List all users
# GET    /api/users/{id}  - Get user by ID
# POST   /api/users/      - Create user (201)
# PATCH  /api/users/{id}  - Update user
# DELETE /api/users/{id}  - Delete user (204)
```

### Custom Hooks

```python
from fastapi import HTTPException
from deebase.api import CRUDRouter

class PostRouter(CRUDRouter):
    async def before_delete(self, pk) -> None:
        """Prevent deleting published posts."""
        table = await self._get_table()
        post = await table[pk]
        if post.get('published'):
            raise HTTPException(400, "Cannot delete published posts")

post_router = PostRouter(db=db, model_cls=Post, prefix="/api/posts", validate_fks=True)
app.include_router(post_router.router)
```

See [API Reference](docs/api_reference.md#api-module-fastapi-integration) for full documentation.

## Command-Line Interface

DeeBase includes a CLI for project management:

```bash
# Initialize a new project
deebase init

# Create table with field:type syntax
deebase table create users id:int name:str email:str:unique --pk id

# Create table with foreign key
deebase table create posts id:int author_id:int:fk=users title:str --pk id --index author_id

# Create table with description and field docstrings (for OpenAPI)
deebase table create articles id:int 'title:str:"Article title"' 'content:Text:"Full content"' \
    --pk id --description "Published articles"

# List tables
deebase table list

# Show table schema
deebase table schema users

# Create view
deebase view create active_users --sql "SELECT * FROM users WHERE status = 'active'"

# Create index
deebase index create users email --unique

# Execute SQL (recorded in migration)
deebase sql "SELECT COUNT(*) FROM users"

# Generate model code from database
deebase codegen

# Migration management
deebase migrate status
deebase migrate seal "initial schema"
deebase migrate up              # Apply all pending migrations
deebase migrate up --to 3       # Apply up to version 3
deebase migrate down -y         # Rollback last migration
deebase migrate down --to 1 -y  # Rollback to version 1

# Database backup
deebase db backup               # Create timestamped backup
deebase db backup --output ./backups/

# Data management (CRUD from terminal)
deebase data list users                  # List records
deebase data insert users -f name=Alice -f email=alice@example.com
deebase data get users 1                 # Get by PK
deebase data update users 1 -f status=inactive
deebase data delete users 1 -y           # Delete (skip confirm)

# REST API (seamless workflow)
deebase api init                # Set up API structure
deebase api generate --all      # Generate full CRUD routers (auto-detects models)
deebase api serve               # Start server at http://127.0.0.1:8000

# Admin interface (no api generate needed)
deebase api serve --admin       # Start with admin at /admin/
```

See `deebase --help` for all commands.

## Examples

Runnable examples are available in the [`examples/`](examples/) folder:

- **[phase1_raw_sql.py](examples/phase1_raw_sql.py)** - Raw SQL queries
- **[phase2_table_creation.py](examples/phase2_table_creation.py)** - Creating tables from Python classes
- **[phase3_crud_operations.py](examples/phase3_crud_operations.py)** - Full CRUD operations
- **[phase4_dataclass_support.py](examples/phase4_dataclass_support.py)** - Type-safe operations with dataclasses
- **[phase5_reflection.py](examples/phase5_reflection.py)** - Working with existing databases
- **[phase7_views.py](examples/phase7_views.py)** - Database views
- **[views_joins_ctes.py](examples/views_joins_ctes.py)** - Using views for JOINs and CTEs
- **[phase8_polish_utilities.py](examples/phase8_polish_utilities.py)** - Error handling & code generation
- **[phase9_transactions.py](examples/phase9_transactions.py)** - Multi-operation atomic transactions
- **[phase10_foreign_keys_defaults.py](examples/phase10_foreign_keys_defaults.py)** - Foreign keys & defaults
- **[phase11_fk_navigation.py](examples/phase11_fk_navigation.py)** - FK relationship navigation
- **[phase12_indexes.py](examples/phase12_indexes.py)** - Query optimization with indexes
- **[phase13_cli.py](examples/phase13_cli.py)** - CLI (demonstrates what CLI does under the hood)
- **[phase14_migrations.py](examples/phase14_migrations.py)** - Database migrations with MigrationRunner
- **[phase15_fastapi.py](examples/phase15_fastapi.py)** - FastAPI integration with CRUD routers
- **[phase16_data_admin.py](examples/phase16_data_admin.py)** - Validation layer and admin interface
- **[complete_example.py](examples/complete_example.py)** - Full-featured blog showcasing all capabilities
- **[complete_example_with_validation.py](examples/complete_example_with_validation.py)** - Blog with validation layer
- **[complete_cli_example.py](examples/complete_cli_example.py)** - End-to-end CLI workflow for building a blog
- **[complete_blog_api_example.py](examples/complete_blog_api_example.py)** - Complete blog REST API with hooks and FK validation
- **[complete_migrations_example.py](examples/complete_migrations_example.py)** - Full migration workflow with CLI

Run any example:
```bash
uv run examples/complete_example.py
```

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
| `ForeignKey[T, "table"]` | FK constraint | References table.id |
| `Index` | INDEX/UNIQUE INDEX | Query optimization |

## Exception Types

| Exception | When Raised | Attributes |
|-----------|-------------|------------|
| `NotFoundError` | Record not found | `table_name`, `filters` |
| `IntegrityError` | Constraint violation | `constraint`, `table_name` |
| `ValidationError` | Invalid input | `field`, `value` |
| `SchemaError` | Schema error | `table_name`, `column_name` |
| `ConnectionError` | Connection failed | `database_url` |
| `InvalidOperationError` | Invalid operation | `operation`, `target` |

## Manual FastAPI Usage

For custom endpoints without CRUD routers:

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

All 539 tests passing ✅

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
│   ├── exceptions.py         # Exception classes
│   └── cli/                  # Command-line interface
│       ├── __init__.py       # Click group and main()
│       ├── init_cmd.py       # deebase init
│       ├── table_cmd.py      # deebase table commands
│       ├── index_cmd.py      # deebase index commands
│       ├── view_cmd.py       # deebase view commands
│       ├── codegen_cmd.py    # deebase codegen
│       ├── migrate_cmd.py    # deebase migrate commands
│       ├── migration_runner.py # MigrationRunner class
│       ├── backup.py         # Database backup functions
│       └── parser.py         # Field:type parser
├── tests/                     # 508 passing tests
├── examples/                  # Runnable examples
├── docs/                      # Documentation
└── README.md                  # This file
```

## Requirements

- Python 3.14+
- sqlalchemy 2.0.45+
- aiosqlite 0.22.0+
- greenlet 3.3.0+ (for SQLAlchemy async)
- click 8.0+ (for CLI)
- toml 0.10+ (for CLI configuration)

## Design Philosophy

DeeBase follows these principles:

1. **Start Simple** - Begin with dicts, opt-in to dataclasses for type safety
2. **Async First** - All operations are async for modern frameworks
3. **Database Agnostic** - Write once, run on SQLite or PostgreSQL
4. **No Magic** - Transparent SQLAlchemy usage with escape hatches
5. **Production Ready** - Comprehensive error handling and testing

## Status

**All 16 development phases complete! Ready for production use.**

- ✅ Phase 1: Core Infrastructure
- ✅ Phase 2: Table Creation & Schema
- ✅ Phase 3: CRUD Operations
- ✅ Phase 4: Dataclass Support
- ✅ Phase 5: Dynamic Access & Reflection
- ✅ Phase 6: xtra() Filtering
- ✅ Phase 7: Views Support
- ✅ Phase 8: Polish & Utilities
- ✅ Phase 9: Transaction Support
- ✅ Phase 10: Foreign Keys & Defaults
- ✅ Phase 11: FK Navigation
- ✅ Phase 12: Indexes
- ✅ Phase 13: Command-Line Interface
- ✅ Phase 14: Migrations
- ✅ Phase 15: FastAPI Integration
- ✅ Phase 16: Data Management & Admin Interface

See [Implementation Plan](docs/implementation_plan.md) for details.

## Contributing

See [docs/implementation_plan.md](docs/implementation_plan.md) for the development roadmap.

## License

TBD

## Acknowledgments

- Inspired by [fastlite](https://fastlite.answer.ai/) by Jeremy Howard
- Built on [SQLAlchemy](https://www.sqlalchemy.org/)
- Async support via [aiosqlite](https://github.com/omnilib/aiosqlite)

---

**Made with ❤️ for the async Python community**
