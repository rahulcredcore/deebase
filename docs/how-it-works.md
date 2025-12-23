# How DeeBase Works: SQLAlchemy Under the Hood

This document explains the technical internals of DeeBase and how it leverages SQLAlchemy to provide an ergonomic async database interface.

## Overview

DeeBase is built on top of **SQLAlchemy Core** (not the ORM) with **async support**. We use SQLAlchemy's:
- Type system for database-agnostic column types
- Metadata system for schema registry
- DDL (Data Definition Language) generation for CREATE/DROP TABLE
- Async engine and sessions for non-blocking database operations
- Dialect system for database-specific SQL generation

This architecture allows DeeBase to support multiple databases (SQLite, PostgreSQL) with a single codebase.

---

## 1. Core SQLAlchemy Classes

### AsyncEngine

The foundation of async database connectivity.

```python
from sqlalchemy.ext.asyncio import create_async_engine

# In Database.__init__
self._engine = create_async_engine(url, echo=False)
# url examples:
#   "sqlite+aiosqlite:///myapp.db"
#   "postgresql+asyncpg://user:pass@localhost/db"
```

**What it does:**
- Manages connection pool
- Handles dialect-specific behavior (SQLite vs PostgreSQL)
- Provides async database operations
- Thread-safe and can be shared across async tasks

**DeeBase usage:** Stored in `Database._engine`, exposed via `db.engine` property.

### MetaData

A registry/catalog for table definitions.

```python
import sqlalchemy as sa

# In Database.__init__
self._metadata = sa.MetaData()
```

**What it does:**
- Acts as a container for `Table` objects
- Maintains relationships between tables
- Provides methods to create/drop all tables
- Required when creating Table objects

**DeeBase usage:** All tables created via `db.create()` are registered with `self._metadata`.

### Table

Represents a database table with its schema.

```python
import sqlalchemy as sa

# Creating a Table object
sa_table = sa.Table(
    'users',                    # table name
    metadata,                   # metadata registry
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('name', sa.String, nullable=False),
    sa.Column('email', sa.String, nullable=True)
)
```

**What it does:**
- Defines table structure (name, columns, constraints)
- Provides access to columns via `.c` or `.columns`
- Can be compiled to SQL via `.compile()`
- Used in DML operations (SELECT, INSERT, UPDATE, DELETE)

**DeeBase usage:**
- Created in `db.create()` and stored in our `Table` wrapper
- Accessed via `table.sa_table` property
- Used for schema generation and future CRUD operations

### Column

Defines a table column with type and constraints.

```python
import sqlalchemy as sa

column = sa.Column(
    'name',                     # column name
    sa.String,                  # column type
    nullable=False,             # constraint
    primary_key=False,          # constraint
    unique=False                # constraint
)
```

**What it does:**
- Specifies column name and data type
- Defines constraints (nullable, primary key, unique, etc.)
- Compiles to SQL column definition
- Provides metadata about the column

**DeeBase usage:** Created dynamically in `db.create()` from Python type annotations.

### AsyncSession

Manages database transactions asynchronously.

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

# In Database.__init__
self._session_factory = sessionmaker(
    self._engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Using a session
async with self._session_factory() as session:
    await session.execute(statement)
    await session.commit()
```

**What it does:**
- Manages transaction lifecycle (begin, commit, rollback)
- Executes SQL statements
- Tracks changes (though we don't use this in DeeBase)
- Provides connection to the database

**DeeBase usage:** Wrapped in `Database._session()` context manager for automatic commit/rollback.

### TypeEngine

SQLAlchemy's type system for database columns.

```python
import sqlalchemy as sa

# Built-in types
sa.Integer()      # INTEGER
sa.String()       # VARCHAR
sa.Text()         # TEXT (unlimited)
sa.Float()        # FLOAT/REAL
sa.Boolean()      # BOOLEAN
sa.JSON()         # JSON (dialect-specific)
sa.DateTime()     # TIMESTAMP/DATETIME
```

**What it does:**
- Represents database column types
- Handles dialect-specific variations
- Provides Python ↔ Database type conversion
- Compiles to SQL type definitions

**DeeBase usage:** Mapped from Python types in `types.py`.

---

## 2. The Type Mapping Pipeline

DeeBase translates Python type hints into database column types through a three-stage pipeline:

### Stage 1: Python Type Annotation

```python
from typing import Optional
from datetime import datetime
from deebase import Text

class Article:
    id: int                      # Python type
    title: str                   # Python type
    content: Text                # Marker class
    metadata: dict               # Python type
    created_at: datetime         # Python type
    excerpt: Optional[str]       # Generic type with None
```

### Stage 2: SQLAlchemy Type

The `python_type_to_sqlalchemy()` function converts Python types:

```python
# In types.py
def python_type_to_sqlalchemy(python_type: type) -> sa.types.TypeEngine:
    # Handle Optional[T]
    origin = get_origin(python_type)
    if origin is not None:
        args = get_args(python_type)
        if type(None) in args:
            # Optional[str] → extract str
            inner_type = args[0] if args[1] is type(None) else args[1]
            return python_type_to_sqlalchemy(inner_type)

    # Check for special marker types
    if python_type is Text:
        return sa.Text()

    # Map basic types
    type_map = {
        int: sa.Integer,
        str: sa.String,
        float: sa.Float,
        dict: sa.JSON,
        datetime: sa.DateTime,
        # ...
    }
    return type_map[python_type]()
```

**Type Resolution:**
- `int` → `sa.Integer()`
- `str` → `sa.String()`
- `Text` → `sa.Text()`
- `dict` → `sa.JSON()`
- `datetime` → `sa.DateTime()`
- `Optional[str]` → `sa.String()` (with nullable=True)

### Stage 3: Database SQL

SQLAlchemy's **dialect system** translates to database-specific SQL:

```python
# When compiled for SQLite:
id: int              → INTEGER
title: str           → TEXT
content: Text        → TEXT
metadata: dict       → TEXT (JSON serialized)
created_at: datetime → TIMESTAMP

# When compiled for PostgreSQL:
id: int              → INTEGER
title: str           → VARCHAR
content: Text        → TEXT
metadata: dict       → JSON (native JSON type)
created_at: datetime → TIMESTAMP
```

**Example: Complete Flow**

```python
# 1. Python class
class User:
    id: int
    name: str
    email: Optional[str]

# 2. In db.create()
annotations = {'id': int, 'name': str, 'email': Optional[str]}

for field_name, field_type in annotations.items():
    # 3. Convert to SQLAlchemy type
    sa_type = python_type_to_sqlalchemy(field_type)
    # id: sa.Integer(), name: sa.String(), email: sa.String()

    # 4. Determine nullability
    nullable = is_optional(field_type)
    # id: False, name: False, email: True

    # 5. Create Column
    col = sa.Column(field_name, sa_type, nullable=nullable)

# 6. Create Table
sa_table = sa.Table('user', metadata, *columns)

# 7. Compile to SQL (dialect-specific)
create_stmt = sa.schema.CreateTable(sa_table)
sql = str(create_stmt.compile(engine))

# SQLite output:
# CREATE TABLE user (
#   id INTEGER NOT NULL PRIMARY KEY,
#   name TEXT NOT NULL,
#   email TEXT
# )
```

---

## 3. Schema Generation & Compilation

### Building a Table from Python

When you call `db.create(cls, pk='id')`, here's what happens:

```python
# 1. Extract annotations
class User:
    id: int
    name: str
    email: str

annotations = extract_annotations(User)
# Returns: {'id': int, 'name': str, 'email': str}

# 2. Build Column objects
columns = []
for field_name, field_type in annotations.items():
    sa_type = python_type_to_sqlalchemy(field_type)
    is_pk = (field_name == 'id')

    col = sa.Column(
        field_name,
        sa_type,
        primary_key=is_pk,
        nullable=False  # PKs are not nullable
    )
    columns.append(col)

# 3. Create SQLAlchemy Table
sa_table = sa.Table(
    'user',              # lowercase class name
    self._metadata,      # metadata registry
    *columns             # unpack column list
)
```

### SQL Generation via compile()

SQLAlchemy's `compile()` method generates database-specific SQL:

```python
from sqlalchemy.schema import CreateTable

# Get SQL for CREATE TABLE
create_table = CreateTable(sa_table)
sql = str(create_table.compile(engine))

# The compile() method:
# 1. Inspects the engine's dialect (sqlite, postgresql, etc.)
# 2. Uses dialect-specific rules to generate SQL
# 3. Handles quoting, type names, and syntax variations
```

**Dialect-Specific Output:**

```python
# SQLite dialect
CREATE TABLE user (
    id INTEGER NOT NULL,
    name VARCHAR NOT NULL,
    email VARCHAR,
    PRIMARY KEY (id)
)

# PostgreSQL dialect
CREATE TABLE "user" (
    id INTEGER NOT NULL,
    name VARCHAR NOT NULL,
    email VARCHAR,
    PRIMARY KEY (id)
)
```

### Schema Property Implementation

```python
# In Table class
@property
def schema(self) -> str:
    """Return the SQL schema definition for this table."""
    from sqlalchemy.schema import CreateTable
    return str(CreateTable(self._sa_table).compile(self._engine))
```

**Usage:**
```python
users = await db.create(User, pk='id')
print(users.schema)  # Shows CREATE TABLE SQL
```

---

## 4. Dynamic Column Access (ColumnAccessor)

DeeBase provides `table.c.column_name` syntax for accessing columns. This is implemented using Python's `__getattr__` magic method.

### How SQLAlchemy Exposes Columns

```python
# SQLAlchemy Table has a .columns collection
sa_table = sa.Table('users', metadata, sa.Column('id', sa.Integer), ...)

# Access via .columns
sa_table.columns['id']      # Get column by name
sa_table.columns.keys()     # List column names
'id' in sa_table.columns    # Check existence

# Access via .c (shorthand)
sa_table.c.id               # Same as columns['id']
sa_table.c['id']            # Same as columns['id']
```

### DeeBase ColumnAccessor

We wrap this with our own accessor that provides additional features:

```python
# In column.py
class ColumnAccessor:
    def __init__(self, sa_table: sa.Table):
        self._sa_table = sa_table

    def __getattr__(self, name: str) -> Column:
        """Dynamic attribute access: table.c.column_name"""
        if name in self._sa_table.columns:
            return Column(self._sa_table.columns[name])
        raise AttributeError(f"No column {name!r}")

    def __dir__(self):
        """Enable auto-complete in IPython/Jupyter"""
        return list(self._sa_table.columns.keys())

    def __iter__(self):
        """Allow iteration: for col in table.c"""
        for col in self._sa_table.columns:
            yield Column(col)
```

### Column Wrapper

Our `Column` class wraps SQLAlchemy's Column with additional features:

```python
class Column:
    def __init__(self, sa_column: sa.Column):
        self.sa_column = sa_column

    def __str__(self) -> str:
        """SQL-safe quoted column name"""
        return f'"{self.sa_column.name}"'

    def __getattr__(self, name: str):
        """Dispatch to underlying sa.Column for any other attributes"""
        return getattr(self.sa_column, name)
```

### Usage Example

```python
users = await db.create(User, pk='id')

# Access via ColumnAccessor
col = users.c.name
# users.c           → ColumnAccessor instance
# users.c.name      → Column wrapper
# col.sa_column     → SQLAlchemy Column
# col.name          → 'name' (dispatched to sa_column)
# col.type          → String() (dispatched to sa_column)
# str(col)          → '"name"' (SQL-safe)

# Iteration
for col in users.c:
    print(col.name, col.type)

# Auto-complete (in IPython/Jupyter)
# users.c.<TAB> shows: id, name, email, etc.
```

---

## 5. Async Session Management

DeeBase uses SQLAlchemy's async sessions for non-blocking database operations.

### Session Factory Pattern

```python
# In Database.__init__
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

self._session_factory = sessionmaker(
    self._engine,               # Async engine
    class_=AsyncSession,        # Use async session class
    expire_on_commit=False      # Don't expire objects after commit
)
```

### Context Manager for Automatic Lifecycle

```python
# In Database class
from contextlib import asynccontextmanager

@asynccontextmanager
async def _session(self):
    """Create an async session with auto commit/rollback"""
    async with self._session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

### Usage in Operations

```python
# In db.q() method
async def q(self, query: str) -> list[dict]:
    async with self._session() as session:
        result = await session.execute(sa.text(query))
        if result.returns_rows:
            return [dict(row._mapping) for row in result.fetchall()]
        return []

# In db.create() method
async def create(self, cls, pk=None):
    # ... build sa_table ...

    async with self._session() as session:
        await session.execute(sa.schema.CreateTable(sa_table))
    # Automatically commits if no exception
```

### Transaction Flow

```
1. async with self._session() as session:
   ↓
2. Session created from factory
   ↓
3. Code executes (yield session)
   ↓
4. If exception: await session.rollback()
   If success: await session.commit()
   ↓
5. Session closes
```

### Why expire_on_commit=False?

By default, SQLAlchemy expires objects after commit, requiring database access to reload them. Since DeeBase doesn't track objects (we return dicts/dataclasses), we disable this:

```python
expire_on_commit=False  # We don't need object tracking
```

---

## 6. Query Execution Flow

### Raw SQL with sa.text()

```python
# In db.q() method
async def q(self, query: str) -> list[dict]:
    async with self._session() as session:
        # Wrap raw SQL string
        result = await session.execute(sa.text(query))

        # Check if query returns rows
        if result.returns_rows:
            # Convert Row objects to dicts
            return [dict(row._mapping) for row in result.fetchall()]
        return []
```

**What `sa.text()` does:**
- Wraps raw SQL string for execution
- Allows parameterization (`:param` syntax)
- Provides safe execution context

### Result Object

```python
result = await session.execute(statement)

# Result attributes:
result.returns_rows      # True for SELECT, False for DDL/DML
result.fetchall()        # List of Row objects
result.fetchone()        # Single Row object
```

### Row to Dict Conversion

```python
# SQLAlchemy Row object
row = result.fetchone()

# Access methods:
row[0]              # By index
row['column']       # By column name
row.column          # By attribute

# Convert to dict
dict(row._mapping)  # {'column': value, ...}
```

**DeeBase approach:**
```python
# We always convert to dicts for consistency
[dict(row._mapping) for row in result.fetchall()]
```

### DDL Execution

```python
# Creating a table
from sqlalchemy.schema import CreateTable

create_stmt = CreateTable(sa_table)
await session.execute(create_stmt)
# Returns result with returns_rows=False

# Dropping a table
from sqlalchemy.schema import DropTable

drop_stmt = DropTable(sa_table)
await session.execute(drop_stmt)
```

---

## 7. Metadata & Caching

### MetaData as Schema Registry

```python
# In Database.__init__
self._metadata = sa.MetaData()

# When creating tables
sa_table = sa.Table('users', self._metadata, *columns)
# Table is automatically registered with metadata

# Metadata provides:
self._metadata.tables           # Dict of all tables
self._metadata.tables['users']  # Get specific table
self._metadata.create_all(engine)  # Create all tables (not used in DeeBase)
```

### DeeBase Table Cache

We maintain our own cache of Table wrapper objects:

```python
# In Database class
self._tables: dict[str, Table] = {}

def _cache_table(self, name: str, table: Table):
    """Cache a Table wrapper"""
    self._tables[name] = table

def _get_table(self, name: str) -> Optional[Table]:
    """Retrieve from cache"""
    return self._tables.get(name)
```

### Relationship Between Classes

```
Database
  ├─ _metadata: sa.MetaData
  │    └─ Holds all sa.Table objects
  │
  ├─ _tables: dict[str, Table]
  │    └─ Cache of our Table wrappers
  │
  └─ Table (our wrapper)
       └─ _sa_table: sa.Table
            └─ The actual SQLAlchemy Table
```

**Example:**
```python
# Create table
users = await db.create(User, pk='id')

# Internally:
# 1. sa.Table created and registered with db._metadata
# 2. Table wrapper created with sa_table
# 3. Wrapper cached in db._tables['user']

# Access later:
cached = db._get_table('user')
assert cached is users

# Access SQLAlchemy table:
sa_table = users.sa_table
# or
sa_table = db._metadata.tables['user']
```

---

## 8. Putting It All Together

### Complete Example: Creating a Table

Let's trace through the entire flow when you call `await db.create(User, pk='id')`:

```python
from deebase import Database, Text
from typing import Optional
from datetime import datetime

# 1. User defines Python class
class Article:
    id: int
    title: str
    content: Text
    metadata: dict
    published: Optional[bool]
    created_at: datetime

# 2. User creates database
db = Database("sqlite+aiosqlite:///blog.db")
# Creates:
# - AsyncEngine with SQLite dialect
# - MetaData registry
# - Session factory
# - Empty table cache

# 3. User creates table
articles = await db.create(Article, pk='id')

# Behind the scenes:
# ==================

# 3a. Extract annotations
annotations = extract_annotations(Article)
# {'id': int, 'title': str, 'content': Text,
#  'metadata': dict, 'published': Optional[bool],
#  'created_at': datetime}

# 3b. Build Column objects
columns = []
for field_name, field_type in annotations.items():
    # Convert Python type → SQLAlchemy type
    sa_type = python_type_to_sqlalchemy(field_type)
    # id: Integer, title: String, content: Text,
    # metadata: JSON, published: Boolean, created_at: DateTime

    # Check if nullable
    nullable = is_optional(field_type)
    # id: False, title: False, ..., published: True, ...

    # Check if PK
    is_pk = (field_name == 'id')

    # Create Column
    col = sa.Column(
        field_name,
        sa_type,
        primary_key=is_pk,
        nullable=nullable and not is_pk
    )
    columns.append(col)

# 3c. Create SQLAlchemy Table
sa_table = sa.Table(
    'article',          # Lowercase class name
    db._metadata,       # MetaData registry
    *columns            # Unpacked columns
)
# Table is now registered in db._metadata.tables['article']

# 3d. Generate and execute CREATE TABLE
async with db._session() as session:
    create_stmt = sa.schema.CreateTable(sa_table)
    # Compiles to dialect-specific SQL:
    # CREATE TABLE article (
    #   id INTEGER NOT NULL,
    #   title VARCHAR NOT NULL,
    #   content TEXT NOT NULL,
    #   metadata TEXT,
    #   published BOOLEAN,
    #   created_at TIMESTAMP NOT NULL,
    #   PRIMARY KEY (id)
    # )

    await session.execute(create_stmt)
    # Session auto-commits on exit

# 3e. Create and cache Table wrapper
articles = Table(
    'article',
    sa_table,
    db._engine,
    dataclass_cls=Article
)
db._cache_table('article', articles)

# 4. User can now access schema
print(articles.schema)
# Calls: CreateTable(sa_table).compile(db._engine)
# Returns SQL string

# 5. User can access columns
for col in articles.c:
    print(col.name, col.type, col.nullable)

# 6. Access underlying SQLAlchemy
sa_table = articles.sa_table
# or
sa_table = db._metadata.tables['article']
```

### Data Flow Diagram

```
User Code
   ↓
 Python Class (with type annotations)
   ↓
extract_annotations() → dict[str, type]
   ↓
python_type_to_sqlalchemy() → sa.TypeEngine
   ↓
sa.Column(name, type, constraints)
   ↓
sa.Table(name, metadata, *columns)
   ↓
sa.schema.CreateTable(table)
   ↓
compile(engine) → SQL string
   ↓
session.execute(create_stmt)
   ↓
Database Table Created
   ↓
Table wrapper returned to user
```

---

## Key Takeaways

1. **SQLAlchemy Core, Not ORM**: We use Tables and Columns directly, not ORM models
2. **Async Throughout**: AsyncEngine, AsyncSession, async operations
3. **Type Safety**: Python types → SQLAlchemy types → Database SQL
4. **Dialect Agnostic**: Same code works for SQLite and PostgreSQL via dialects
5. **Wrapper Pattern**: We wrap SQLAlchemy objects (Table, Column) with our own classes
6. **Metadata Registry**: MetaData tracks all table definitions
7. **Session Per Operation**: Each operation gets its own session with auto-commit
8. **Compile for SQL**: Use `.compile(engine)` to generate database-specific SQL

## Further Reading

- [SQLAlchemy Core Documentation](https://docs.sqlalchemy.org/en/20/core/)
- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [SQLAlchemy Type System](https://docs.sqlalchemy.org/en/20/core/types.html)
- [SQLAlchemy Dialects](https://docs.sqlalchemy.org/en/20/dialects/)
