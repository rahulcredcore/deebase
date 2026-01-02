# DeeBase CLI Reference

This document provides a complete reference for the DeeBase command-line interface (CLI). The CLI enables project management, schema changes, code generation, and migration workflows directly from the terminal.

## Table of Contents

- [Installation & Usage](#installation--usage)
- [When to Use the CLI](#when-to-use-the-cli)
- [Commands Reference](#commands-reference)
  - [init](#init)
  - [table](#table)
  - [index](#index)
  - [view](#view)
  - [db](#db)
  - [sql](#sql)
  - [codegen](#codegen)
  - [migrate](#migrate)
- [Configuration](#configuration)
- [Migration Workflow](#migration-workflow)
- [Common Workflows](#common-workflows)

---

## Installation & Usage

The CLI is included with DeeBase. After installing the package:

```bash
# Using uv (recommended)
uv run deebase <command>

# If installed globally
deebase <command>

# Get help
deebase --help
deebase <command> --help
```

---

## When to Use the CLI

### Use the CLI When...

| Scenario | Why CLI is Better |
|----------|-------------------|
| **Project setup** | `deebase init` creates the proper directory structure and config files |
| **Quick prototyping** | Create tables interactively without writing Python code |
| **Schema iteration** | Rapidly add/modify tables during development |
| **Database inspection** | Check table schemas, list views, see database info |
| **Migration management** | Seal migrations, check status, create new migration files |
| **Code generation** | Generate Python models from existing database schema |
| **Ad-hoc queries** | Run quick SQL queries without writing a script |
| **Team onboarding** | New team members can understand schema via CLI |

### Use the Python API Instead When...

| Scenario | Why Python API is Better |
|----------|-------------------------|
| **Application code** | Python API integrates with your async application |
| **Complex logic** | Business logic, validation, computed fields |
| **Type safety** | IDE autocomplete, mypy/pyright checking |
| **Programmatic control** | Conditional table creation, dynamic schemas |
| **Transactions** | Multi-operation atomicity with `db.transaction()` |
| **FK navigation** | `table.fk.column(record)` for relationship traversal |
| **Bulk operations** | Large inserts, batch updates, streaming |
| **Testing** | Unit tests, integration tests with fixtures |

### CLI + Python API Together

The CLI and Python API are complementary:

```bash
# CLI: Set up project and schema
deebase init
deebase table create users id:int name:str email:str:unique --pk id
deebase codegen
```

```python
# Python: Application code
from deebase import Database
from models import Users

db = Database("sqlite+aiosqlite:///app.db")
await db.reflect()
users = db.t.users

# Type-safe operations
user = await users.insert({"name": "Alice", "email": "alice@example.com"})
```

---

## Commands Reference

### init

Initialize a new DeeBase project.

```bash
deebase init [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--package NAME` | Integrate with existing Python package |
| `--new-package NAME` | Create new Python package |
| `--postgres` | Use PostgreSQL instead of SQLite |

**What it creates:**

```
project/
├── deebase.yaml       # Configuration file
├── .env               # Environment variables (DATABASE_URL)
├── migrations/        # Migration files directory
└── models/            # Generated models directory
```

**Examples:**

```bash
# Basic initialization
deebase init

# With existing package
deebase init --package myapp

# Create new package
deebase init --new-package myapp

# PostgreSQL project
deebase init --postgres
```

**When to use:**
- Starting a new DeeBase project
- Adding DeeBase to an existing project

**When NOT to use:**
- If you already have a `deebase.yaml` file
- If you want to use DeeBase without migrations (just use Python API directly)

---

### table

Table management commands.

#### table create

Create a new database table.

```bash
deebase table create NAME FIELDS... [OPTIONS]
```

**Field Format:** `name:type:modifier1:modifier2...`

**Types:**

| Type | SQL Type | Example |
|------|----------|---------|
| `int` | INTEGER | `id:int` |
| `str` | VARCHAR | `name:str` |
| `Text` | TEXT | `content:Text` |
| `float` | REAL/FLOAT | `price:float` |
| `bool` | BOOLEAN | `active:bool` |
| `bytes` | BLOB | `data:bytes` |
| `dict` | JSON | `metadata:dict` |
| `datetime` | TIMESTAMP | `created_at:datetime` |
| `date` | DATE | `birth_date:date` |
| `time` | TIME | `start_time:time` |

**Modifiers:**

| Modifier | Description | Example |
|----------|-------------|---------|
| `unique` | UNIQUE constraint | `email:str:unique` |
| `nullable` | Allow NULL values | `bio:Text:nullable` |
| `default=VALUE` | Default value | `status:str:default=active` |
| `fk=TABLE` | Foreign key to table.id | `author_id:int:fk=users` |
| `fk=TABLE.COL` | Foreign key to specific column | `category:str:fk=categories.slug` |

**Options:**

| Option | Description |
|--------|-------------|
| `--pk COLUMN` | Primary key column(s), comma-separated |
| `--index COLUMNS` | Create index on column(s) |

**Examples:**

```bash
# Simple table
deebase table create users id:int name:str email:str --pk id

# With modifiers
deebase table create users \
    id:int \
    name:str \
    email:str:unique \
    bio:Text:nullable \
    status:str:default=active \
    --pk id

# With foreign key and index
deebase table create posts \
    id:int \
    author_id:int:fk=users \
    title:str \
    content:Text \
    views:int:default=0 \
    --pk id \
    --index author_id

# Composite primary key
deebase table create order_items \
    order_id:int:fk=orders \
    product_id:int:fk=products \
    quantity:int:default=1 \
    --pk order_id,product_id
```

**When to use:**
- Rapid prototyping and schema iteration
- Setting up initial database schema
- Adding new tables during development

**When NOT to use:**
- Tables with complex validation logic (use Python API)
- Dynamic schema based on runtime conditions

#### table list

List all tables in the database.

```bash
deebase table list
```

**Output:**
```
Tables:
  users
  posts
  comments
```

#### table schema

Show the CREATE TABLE statement for a table.

```bash
deebase table schema NAME
```

**Example:**
```bash
deebase table schema users
```

**Output:**
```sql
CREATE TABLE users (
  id INTEGER NOT NULL,
  name VARCHAR NOT NULL,
  email VARCHAR NOT NULL,
  bio TEXT,
  status VARCHAR DEFAULT 'active',
  PRIMARY KEY (id)
)
```

#### table drop

Drop a table from the database.

```bash
deebase table drop NAME [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--yes, -y` | Skip confirmation prompt |

**Example:**
```bash
deebase table drop old_table --yes
```

**Warning:** This permanently deletes the table and all its data!

---

### index

Index management commands.

#### index create

Create an index on a table.

```bash
deebase index create TABLE COLUMNS [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--name NAME` | Custom index name (auto-generated if not specified) |
| `--unique` | Create unique index |

**Examples:**

```bash
# Simple index (auto-named: ix_posts_title)
deebase index create posts title

# Composite index
deebase index create posts author_id,created_at

# Unique index with custom name
deebase index create users email --unique --name ix_users_email
```

**Auto-generated names:** `ix_{tablename}_{column1}_{column2}...`

**When to use:**
- Adding indexes to optimize frequently-queried columns
- Creating unique constraints on columns

**When NOT to use:**
- Primary key columns (already indexed)
- Rarely-queried columns (indexes have write overhead)

#### index list

List all indexes on a table.

```bash
deebase index list TABLE
```

**Output:**
```
Indexes on 'posts':
  ix_posts_author_id: author_id
  ix_posts_title: title (unique)
```

#### index drop

Drop an index.

```bash
deebase index drop NAME [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--yes, -y` | Skip confirmation prompt |

**Example:**
```bash
deebase index drop ix_old_index --yes
```

---

### view

View management commands.

#### view create

Create a database view.

```bash
deebase view create NAME --sql "SELECT ..." [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--sql SQL` | SQL SELECT query for the view (required) |
| `--replace` | Replace existing view if it exists |

**Examples:**

```bash
# Simple filter view
deebase view create active_users \
    --sql "SELECT * FROM users WHERE status = 'active'"

# View with JOIN
deebase view create posts_with_authors \
    --sql "SELECT p.id, p.title, p.views, u.name as author
           FROM posts p JOIN users u ON p.author_id = u.id"

# Replace existing view
deebase view create active_users \
    --sql "SELECT * FROM users WHERE active = 1" \
    --replace
```

**When to use:**
- Frequently-used JOIN queries
- Complex filters you want to reuse
- Providing simplified access to derived data

**When NOT to use:**
- One-off queries (use `deebase sql` instead)
- Queries that need parameters (views are static)

#### view list

List all views in the database.

```bash
deebase view list
```

#### view reflect

Reflect an existing view created outside DeeBase.

```bash
deebase view reflect NAME
```

**Example:**
```bash
deebase view reflect legacy_report_view
```

#### view drop

Drop a view.

```bash
deebase view drop NAME [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--yes, -y` | Skip confirmation prompt |

---

### db

Database information commands.

#### db info

Show database information.

```bash
deebase db info
```

**Output:**
```
Database: SQLite
Location: /path/to/project/app.db
Tables: users, posts, comments
Views: active_users, posts_with_authors
Size: 128.5 KB
```

---

### sql

Execute raw SQL queries.

```bash
deebase sql "SQL QUERY" [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--no-record` | Don't record in migration file |

**Examples:**

```bash
# Query (not recorded by default for SELECT)
deebase sql "SELECT COUNT(*) FROM users"

# DDL recorded in migration
deebase sql "CREATE INDEX ix_custom ON users(name)"

# Explicit no-record (useful for INSERT/UPDATE during dev)
deebase sql "INSERT INTO users (name, email) VALUES ('Test', 'test@example.com')" --no-record
```

**When to use:**
- Ad-hoc queries during development
- Custom SQL that DeeBase doesn't generate
- Quick data inspection

**When NOT to use:**
- Application code (use Python API)
- Complex transactions (use Python API with `db.transaction()`)

---

### codegen

Generate Python dataclass models from database tables.

```bash
deebase codegen [TABLES...] [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--output, -o PATH` | Custom output file path |

**Examples:**

```bash
# Generate from all tables
deebase codegen

# Generate specific tables
deebase codegen users posts

# Custom output path
deebase codegen --output src/myapp/db/models.py
```

**Generated Output:**

```python
"""Auto-generated database models from DeeBase."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Users:
    id: Optional[int] = None
    name: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None


@dataclass
class Posts:
    id: Optional[int] = None
    author_id: Optional[int] = None
    title: Optional[str] = None
    content: Optional[str] = None
```

**When to use:**
- Initial model generation for a new project
- Updating models after schema changes
- Documenting existing database schema

**When NOT to use:**
- If you maintain models manually with custom logic
- If models have significant customizations (regenerating will overwrite)

---

### migrate

Migration management commands.

#### migrate status

Show current migration status.

```bash
deebase migrate status
```

**Output:**
```
Migration Status:
  Current: 001_initial.py (unsealed - can be modified)
  Pending operations: 5

Sealed migrations:
  (none)
```

#### migrate seal

Seal the current migration and create a new one.

```bash
deebase migrate seal "DESCRIPTION"
```

**Example:**
```bash
deebase migrate seal "initial blog schema"
```

**What happens:**
1. Current migration file is renamed with the description
2. Migration is marked as sealed (won't be modified)
3. New empty migration file is created

#### migrate new

Create a new empty migration file.

```bash
deebase migrate new "DESCRIPTION"
```

**Example:**
```bash
deebase migrate new "add comments table"
```

---

## Configuration

### deebase.yaml

```yaml
# Database configuration
database:
  type: sqlite              # sqlite or postgres
  name: app.db              # Database name/file

# Output paths
models_output: models/models.py
migrations_dir: migrations

# Optional: integrate with existing package
# package: myapp
```

### Environment Variables (.env)

```bash
# SQLite
DATABASE_URL=sqlite+aiosqlite:///app.db

# PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:password@localhost/mydb

# PostgreSQL with SSL
DATABASE_URL=postgresql+asyncpg://user:password@host/db?ssl=require
```

**Note:** `DATABASE_URL` takes precedence over `deebase.yaml` database settings.

---

## Migration Workflow

DeeBase uses a **sealed/unsealed** migration workflow:

### Understanding the Workflow

```
┌─────────────────────────────────────────────────────────┐
│                    DEVELOPMENT                          │
│  CLI commands append to UNSEALED migration              │
│  (001_initial.py - can be modified)                     │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼ deebase migrate seal "description"
┌─────────────────────────────────────────────────────────┐
│                    SEALED                               │
│  Migration is frozen (001_initial_blog_schema.py)       │
│  New unsealed migration created (002_*.py)              │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    DEPLOYMENT                           │
│  Run sealed migrations on target database               │
│  (Phase 14: deebase migrate up)                         │
└─────────────────────────────────────────────────────────┘
```

### Development Cycle

```bash
# 1. Start development
deebase init
deebase table create users id:int name:str email:str:unique --pk id
# → Operations recorded in 001_initial.py (unsealed)

# 2. Iterate on schema
deebase table create posts id:int author_id:int:fk=users title:str --pk id
deebase index create posts title
# → More operations appended to 001_initial.py

# 3. Ready to deploy - seal the migration
deebase migrate seal "initial blog schema"
# → 001_initial.py renamed to 001_initial_blog_schema.py (sealed)
# → 002_*.py created (new unsealed)

# 4. Continue development
deebase table create comments id:int post_id:int:fk=posts content:Text --pk id
# → Operations go to 002_*.py

# 5. Ready for next deployment
deebase migrate seal "add comments"
# → 002_add_comments.py (sealed)
# → 003_*.py created (new unsealed)
```

### Migration File Format

```python
"""Migration: initial_blog_schema

Created: 2024-01-15 10:30:00
DeeBase migration file - uses async DeeBase API.
"""


async def up(db):
    """Apply migration."""
    # Auto-generated from CLI commands
    class Users:
        id: int
        name: str
        email: str

    await db.create(Users, pk='id')

    class Posts:
        id: int
        author_id: ForeignKey[int, "users"]
        title: str

    await db.create(Posts, pk='id')
    await db.t.posts.create_index("title")


async def down(db):
    """Revert migration."""
    await db.t.posts.drop()
    await db.t.users.drop()
```

---

## Common Workflows

### Starting a New Project

```bash
# Initialize
deebase init

# Create schema
deebase table create users id:int name:str email:str:unique --pk id
deebase table create posts id:int author_id:int:fk=users title:str content:Text --pk id
deebase index create posts author_id

# Generate models
deebase codegen

# Seal for deployment
deebase migrate seal "initial schema"
```

### Adding Features

```bash
# Add new table
deebase table create comments \
    id:int \
    post_id:int:fk=posts \
    user_id:int:fk=users \
    content:Text \
    --pk id

# Add indexes
deebase index create comments post_id
deebase index create comments user_id

# Regenerate models
deebase codegen

# Seal when ready
deebase migrate seal "add comments"
```

### Database Inspection

```bash
# Overview
deebase db info

# List everything
deebase table list
deebase view list
deebase index list posts

# Detailed schema
deebase table schema users
```

### Quick Data Operations

```bash
# Insert test data
deebase sql "INSERT INTO users (name, email) VALUES ('Alice', 'alice@test.com')" --no-record

# Query data
deebase sql "SELECT * FROM users"

# Check counts
deebase sql "SELECT COUNT(*) FROM posts WHERE author_id = 1"
```

---

## Error Messages

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "No DeeBase project found" | No `deebase.yaml` in directory tree | Run `deebase init` |
| "Table 'X' already exists" | Duplicate table creation | Use `--replace` or drop first |
| "Foreign key table 'X' not found" | Referenced table doesn't exist | Create parent table first |
| "Column 'X' not found" | Invalid column in index/schema | Check column name spelling |
| "Migration is sealed" | Trying to modify sealed migration | Create new migration with `migrate new` |

### Getting Help

```bash
# General help
deebase --help

# Command-specific help
deebase table --help
deebase table create --help
deebase migrate --help
```

---

## See Also

- [API Reference](api_reference.md) - Python API documentation
- [Best Practices](best-practices.md) - CLI and API usage patterns
- [Implemented Features](implemented.md) - Complete feature guide
- [Implementation Plan](implementation_plan.md) - Roadmap and future plans
