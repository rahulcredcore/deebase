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

## 9. CRUD Operations (Phase 3)

Phase 3 implements full CRUD operations using SQLAlchemy Core DML (Data Manipulation Language) statements. All operations follow a consistent pattern: create session → build statement → execute → fetch results → return processed data.

### Insert Operation

**What it does:**
Inserts a record and returns the full inserted row (including auto-generated values like auto-increment IDs).

**SQLAlchemy operations used:**
```python
# In Table.insert()
stmt = sa.insert(self._sa_table).values(**data)
result = await session.execute(stmt)

# Get auto-generated primary key
inserted_pk = result.inserted_primary_key  # Tuple of PK values

# Fetch complete record with generated values
select_stmt = sa.select(self._sa_table).where(
    pk_col == inserted_pk[0]
)
row = (await session.execute(select_stmt)).fetchone()
```

**Key techniques:**
- `sa.insert()` creates an INSERT statement
- `result.inserted_primary_key` provides auto-generated PK values
- Follow-up SELECT fetches the complete record with defaults/triggers
- Handles composite PKs by building WHERE clause for all PK columns

**Flow:**
```
user input (dict/dataclass)
   ↓
_from_input() → converts to dict
   ↓
Validate xtra filters (auto-set if missing)
   ↓
Build INSERT statement with sa.insert()
   ↓
Execute and get inserted_primary_key
   ↓
SELECT to fetch complete row
   ↓
_to_record() → dict or dataclass
```

### Update Operation

**What it does:**
Updates a record by primary key and returns the updated row.

**SQLAlchemy operations used:**
```python
# In Table.update()
stmt = sa.update(self._sa_table)

# WHERE clause for PK
for pk_col in pk_cols:
    stmt = stmt.where(pk_col == pk_values[pk_col.name])

# Apply xtra filters to WHERE
for col_name, value in self._xtra_filters.items():
    stmt = stmt.where(self._sa_table.c[col_name] == value)

# Set new values (excluding PK columns)
stmt = stmt.values(**update_data)

result = await session.execute(stmt)

# Check if row was updated
if result.rowcount == 0:
    raise NotFoundError(...)
```

**Key techniques:**
- `sa.update()` creates an UPDATE statement
- `.where()` adds WHERE conditions (PK + xtra filters)
- `.values()` sets the new column values
- `result.rowcount` detects if record existed
- Follow-up SELECT fetches the updated record

**Flow:**
```
user input with PK
   ↓
Extract PK values from record
   ↓
Build UPDATE with WHERE (PK + xtra)
   ↓
Execute and check rowcount
   ↓
Raise NotFoundError if rowcount == 0
   ↓
SELECT to fetch updated row
   ↓
Return processed record
```

### Delete Operation

**What it does:**
Deletes a record by primary key (or composite PK tuple).

**SQLAlchemy operations used:**
```python
# In Table.delete()
stmt = sa.delete(self._sa_table)

# WHERE clause for PK(s)
for i, pk_col in enumerate(pk_cols):
    stmt = stmt.where(pk_col == pk_values[i])

# Apply xtra filters
for col_name, value in self._xtra_filters.items():
    stmt = stmt.where(self._sa_table.c[col_name] == value)

result = await session.execute(stmt)

if result.rowcount == 0:
    raise NotFoundError(...)
```

**Key techniques:**
- `sa.delete()` creates a DELETE statement
- Multiple `.where()` calls for composite PKs
- `result.rowcount` detects if record was found
- xtra filters prevent deleting wrong user's data

### Select Operations

**What they do:**
- `table()` → SELECT all or limited records
- `table[pk]` → SELECT single record by primary key
- `table.lookup(**kwargs)` → SELECT single record by WHERE conditions

**SQLAlchemy operations used:**
```python
# SELECT all/limited
stmt = sa.select(self._sa_table)
stmt = stmt.where(...)  # Apply xtra filters
stmt = stmt.limit(N)    # Optional limit
rows = (await session.execute(stmt)).fetchall()

# SELECT by PK
stmt = sa.select(self._sa_table).where(pk_col == pk_value)
row = (await session.execute(stmt)).fetchone()

# SELECT with WHERE conditions
stmt = sa.select(self._sa_table)
for col_name, value in filters.items():
    stmt = stmt.where(self._sa_table.c[col_name] == value)
row = (await session.execute(stmt)).fetchone()
```

**Key techniques:**
- `sa.select(table)` creates a SELECT statement
- `.where(column == value)` adds WHERE conditions
- `.limit(N)` adds LIMIT clause
- `.fetchall()` for multiple rows, `.fetchone()` for single row
- `row._mapping` converts Row to dict-like object

**with_pk parameter:**
```python
# When with_pk=True, return (pk_value, record) tuples
results = []
for row in rows:
    record = self._to_record(row)
    if len(pk_cols) == 1:
        pk_value = row._mapping[pk_cols[0].name]
    else:
        pk_value = tuple(row._mapping[pk_col.name] for pk_col in pk_cols)
    results.append((pk_value, record))
```

### Upsert Operation

**What it does:**
Inserts if PK doesn't exist, updates if it does.

**Implementation strategy:**
```python
# In Table.upsert()
# 1. Check if PK is provided
if not has_pk:
    return await self.insert(record)

# 2. Check if record exists with SELECT
select_stmt = sa.select(self._sa_table).where(...)
existing = (await session.execute(select_stmt)).fetchone()

# 3. Route to insert or update
if existing:
    return await self.update(record)
else:
    return await self.insert(record)
```

**Why not dialect-specific upsert?**
- SQLite: `INSERT OR REPLACE`
- PostgreSQL: `INSERT ... ON CONFLICT`
- Our approach: SELECT → INSERT/UPDATE
  - ✅ Database-agnostic
  - ✅ Simpler logic
  - ✅ Reuses existing methods
  - ⚠️ Slightly less efficient (extra query)

### Composite Primary Keys

All CRUD operations handle composite PKs:

**Insert:** Returns tuple from `inserted_primary_key`
```python
inserted_pk = (1, 101)  # (order_id, item_id)
```

**Get/Delete:** Accept tuple as input
```python
item = await table[(1, 101)]        # GET
await table.delete((1, 101))        # DELETE
```

**Update:** Extract all PK values from record dict
```python
# record = {"order_id": 1, "item_id": 101, "quantity": 10}
for pk_col in pk_cols:
    pk_values[pk_col.name] = data[pk_col.name]
```

### xtra() Filtering

The `xtra()` method returns a new Table instance with filters:

```python
# In Table.xtra()
return Table(
    self._name,
    self._sa_table,      # Same SQLAlchemy table
    self._engine,        # Same engine
    self._dataclass_cls, # Same dataclass
    new_filters          # DIFFERENT filters
)
```

**How filters are applied:**

Every SELECT/UPDATE/DELETE adds WHERE conditions:
```python
# Applied in all operations
for col_name, value in self._xtra_filters.items():
    stmt = stmt.where(self._sa_table.c[col_name] == value)
```

**INSERT auto-sets filter values:**
```python
# In insert(), before executing
for col_name, expected_value in self._xtra_filters.items():
    data[col_name] = expected_value  # Auto-set
```

**Prevents cross-user data access:**
```python
user1_posts = posts.xtra(user_id=1)

# Can only see/modify user_id=1 posts
await user1_posts.delete(post_id)  # Only deletes if user_id=1
```

### Record Conversion (_to_record and _from_input)

**_from_input():** Converts any input to dict
```python
def _from_input(self, record: Any) -> dict:
    return record_to_dict(record)
    # Handles: dict (pass-through), dataclass (asdict), object (__dict__)
```

**_to_record():** Converts Row to dict or dataclass
```python
def _to_record(self, row: sa.Row) -> dict | Any:
    data = dict(row._mapping)
    if self._dataclass_cls and is_dataclass(self._dataclass_cls):
        return dict_to_dataclass(data, self._dataclass_cls)
    return data
```

**When are dataclasses used?**
- Only when `_dataclass_cls` is set AND is an actual dataclass
- Set by `db.create(ActualDataclass)` or `table.dataclass()`
- Plain annotation classes (not @dataclass) return dicts

### Error Handling with NotFoundError

All operations that expect to find records raise `NotFoundError` when missing:

```python
# After UPDATE/DELETE
if result.rowcount == 0:
    raise NotFoundError(f"Record with PK {pk_value} not found")

# After SELECT
if row is None:
    raise NotFoundError(f"No record found matching {kwargs}")
```

**User code:**
```python
try:
    user = await users[999]
except NotFoundError:
    print("User not found")
```

### Session Management Pattern

All CRUD operations follow this pattern:

```python
# Create session factory
session_factory = sessionmaker(
    self._engine,
    class_=AsyncSession,
    expire_on_commit=False  # Keep objects usable after commit
)

# Use session
async with session_factory() as session:
    try:
        # Execute operations
        result = await session.execute(stmt)
        await session.commit()
        return processed_result
    except Exception:
        await session.rollback()
        raise
```

**Why this pattern?**
- ✅ Each operation is atomic
- ✅ Auto-rollback on errors
- ✅ No connection leaks
- ✅ Thread-safe (each operation gets own session)

### Performance Considerations

**Insert:** 2 queries (INSERT + SELECT for complete row)
- Necessary to get auto-generated values (auto-increment, defaults, triggers)

**Update:** 2 queries (UPDATE + SELECT for updated row)
- Could optimize to return data directly, but SELECT ensures consistency

**Upsert:** 3 queries (SELECT + INSERT/UPDATE + SELECT)
- Trade-off: database-agnostic vs performance

**Select:** 1 query
- Efficient: single SELECT with WHERE/LIMIT

**Delete:** 1 query
- Efficient: single DELETE with WHERE

**Future optimization opportunities:**
- RETURNING clause support (PostgreSQL, SQLite 3.35+)
- Batch operations (insertmany, updatemany)
- Compiled statement caching

---

## 10. Dataclass Support (Phase 4)

Phase 4 adds dataclass support for type-safe database operations. The key is the `.dataclass()` method which generates a dataclass from table metadata or returns an existing one.

### The .dataclass() Method

**What it does:**
Generates a dataclass from SQLAlchemy table metadata using `make_table_dataclass()`.

**Implementation:**
```python
def dataclass(self) -> type:
    from dataclasses import is_dataclass

    # If _dataclass_cls is not set, or is set but not an actual dataclass,
    # generate a new dataclass from the table metadata
    if self._dataclass_cls is None or not is_dataclass(self._dataclass_cls):
        self._dataclass_cls = make_table_dataclass(self._name, self._sa_table)
    return self._dataclass_cls
```

**Key logic:**
1. Check if `_dataclass_cls` exists and is an actual `@dataclass`
2. If not, generate new dataclass using `make_table_dataclass()`
3. Cache the generated dataclass on the Table instance
4. Return the dataclass type

**Why the `is_dataclass()` check?**
When `db.create(User)` is called with a plain annotation class:
- `_dataclass_cls` is set to `User` (plain class, not `@dataclass`)
- Later calling `.dataclass()` needs to generate a real dataclass
- Without the check, it would return the plain class

### make_table_dataclass()

**Purpose:** Generate a dataclass from SQLAlchemy Table metadata

**Implementation:**
```python
def make_table_dataclass(table_name: str, sa_table: sa.Table) -> type:
    # Map SQLAlchemy types back to Python types
    field_definitions = []

    for column in sa_table.columns:
        python_type = sqlalchemy_type_to_python(column.type)

        # Make all fields Optional (default to None) to handle auto-generated values
        field_definitions.append((column.name, python_type | None, None))

    # Create the dataclass
    return make_dataclass(
        table_name.capitalize(),
        field_definitions,
        frozen=False
    )
```

**Key decisions:**
- All fields are `Optional` (with `None` default) to handle auto-increment PKs
- Uses Python's `make_dataclass()` for dynamic generation
- Field types reverse-mapped from SQLAlchemy types

**Type reverse-mapping:**
```python
sa.Integer → int
sa.String → str
sa.Text → str
sa.Float → float
sa.Boolean → bool
sa.JSON → dict
sa.DateTime → datetime
```

### How CRUD Operations Use Dataclasses

**_to_record() - Output conversion:**
```python
def _to_record(self, row: sa.Row) -> dict | Any:
    from dataclasses import is_dataclass

    data = dict(row._mapping)
    # Only convert to dataclass if the class is actually a dataclass
    if self._dataclass_cls and is_dataclass(self._dataclass_cls):
        return dict_to_dataclass(data, self._dataclass_cls)
    return data
```

**Flow:**
```
SQLAlchemy Row
   ↓
row._mapping → dict
   ↓
is_dataclass(_dataclass_cls)?
   ├─ Yes → dict_to_dataclass() → dataclass instance
   └─ No  → return dict
```

**_from_input() - Input conversion:**
```python
def _from_input(self, record: Any) -> dict:
    return record_to_dict(record)
    # Handles: dict (pass-through), dataclass (asdict), object (__dict__)
```

**Supported inputs:**
- `dict` → pass through
- `@dataclass` instance → `asdict()` → dict
- Plain object → `__dict__` → dict

### Using @dataclass with db.create()

```python
@dataclass
class User:
    id: Optional[int] = None
    name: str = ""
    email: str = ""

users = await db.create(User, pk='id')
# _dataclass_cls = User (actual @dataclass)
# is_dataclass(User) = True
```

**Flow:**
1. `db.create(User)` sets `_dataclass_cls = User`
2. `User` is an actual `@dataclass` (decorated)
3. `_to_record()` checks `is_dataclass(User)` → True
4. All operations return `User` instances automatically
5. Calling `.dataclass()` returns `User` (already a dataclass)

### Using Plain Class with db.create()

```python
class User:
    id: int
    name: str
    email: str

users = await db.create(User, pk='id')
# _dataclass_cls = User (plain annotation class)
# is_dataclass(User) = False
```

**Flow without `.dataclass()`:**
1. `db.create(User)` sets `_dataclass_cls = User`
2. `User` is NOT a `@dataclass`
3. `_to_record()` checks `is_dataclass(User)` → False
4. Operations return dicts

**Flow after `.dataclass()`:**
1. Call `users.dataclass()`
2. Check `is_dataclass(User)` → False
3. Generate new dataclass via `make_table_dataclass()`
4. Replace `_dataclass_cls` with generated dataclass
5. All subsequent operations return dataclass instances

### Benefits of This Design

**Flexibility:**
- Start with dicts (simple, no ceremony)
- Opt-in to dataclasses when needed (type safety)
- Supports both `@dataclass` and plain classes

**Type Safety:**
- IDE autocomplete on dataclass fields
- Static type checking with mypy/pyright
- Runtime field validation

**Ergonomics:**
- Single method call (`.dataclass()`) enables type safety
- Works with existing code (can mix dicts and dataclasses)
- Generated dataclasses handle auto-increment PKs

**Performance:**
- Dataclass generation happens once (cached)
- `is_dataclass()` check is O(1)
- No overhead when using dicts

---

## 11. Reflection & Dynamic Access (Phase 5)

Phase 5 enables working with existing databases by reflecting table metadata and providing dynamic table access.

### The Async/Sync Challenge

**Original Design Goal:** Lazy loading via `db.t.tablename`
```python
# Desired: lazy table loading on first access
users = db.t.users  # Would auto-reflect the users table
```

**The Problem:** Python's `__getattr__` is synchronous, but SQLAlchemy's reflection with `AsyncEngine` requires async operations.

**Solution:** Explicit reflection + fast synchronous cache access.

### Database.reflect() - Reflect All Tables

**What it does:**
Async method that discovers and loads all tables from the database into the cache.

**Implementation:**
```python
async def reflect(self):
    """Reflect all tables from database."""
    # Use SQLAlchemy's reflect() to discover tables
    async with self._engine.begin() as conn:
        await conn.run_sync(self._metadata.reflect)

    # Wrap each reflected table in our Table class
    for table_name, sa_table in self._metadata.tables.items():
        if table_name not in self._tables:  # Skip already cached
            table = Table(table_name, sa_table, self._engine)
            self._tables[table_name] = table
```

**How SQLAlchemy Reflection Works:**

1. **Metadata.reflect()** inspects the database schema
2. Queries `information_schema` (PostgreSQL) or `sqlite_master` (SQLite)
3. Creates `sa.Table` objects with columns, types, constraints
4. Registers tables in the `MetaData` object
5. Preserves full schema including primary keys, nullable columns, etc.

**Example:**
```python
# Database already has tables from previous sessions
db = Database("sqlite+aiosqlite:///myapp.db")

# Reflect all tables (one-time async operation)
await db.reflect()

# Now access is synchronous and fast (cache lookups)
users = db.t.users      # Cache hit - no database query
posts = db.t.posts      # Cache hit - no database query
```

### Database.reflect_table() - Single Table Reflection

**What it does:**
Async method that reflects a specific table by name.

**Implementation:**
```python
async def reflect_table(self, name: str) -> Table:
    """Reflect a single table from the database."""
    # Check cache first
    if name in self._tables:
        return self._tables[name]

    # Reflect the specific table
    async with self._engine.begin() as conn:
        sa_table = await conn.run_sync(
            lambda sync_conn: sa.Table(
                name,
                self._metadata,
                autoload_with=sync_conn
            )
        )

    # Wrap and cache
    table = Table(name, sa_table, self._engine)
    self._tables[name] = table
    return table
```

**Use case:** When you create a table with raw SQL during a session:
```python
# Create table with raw SQL
await db.q("CREATE TABLE products (id INT PRIMARY KEY, name TEXT)")

# Reflect just this table
products = await db.reflect_table('products')

# Now accessible via db.t
products = db.t.products  # Cache hit
```

### TableAccessor - Cache-Only Dynamic Access

**What it does:**
Provides `db.t.tablename` syntax for accessing cached tables (synchronous).

**Implementation:**
```python
class TableAccessor:
    def __init__(self, db: Database):
        self._db = db

    def __getattr__(self, name: str) -> Table:
        """Access table by attribute: db.t.users"""
        if name in self._db._tables:
            return self._db._tables[name]

        # Helpful error message
        raise AttributeError(
            f"Table '{name}' not found in cache. "
            f"Use 'await db.reflect()' to load all tables, "
            f"or 'await db.reflect_table(\"{name}\")' to load this table."
        )

    def __getitem__(self, key):
        """Access table(s) by index: db.t['users'] or db.t['users', 'posts']"""
        if isinstance(key, str):
            return self.__getattr__(key)

        # Multiple tables: db.t['users', 'posts']
        if isinstance(key, tuple):
            return tuple(self.__getattr__(name) for name in key)
```

**Why Cache-Only?**
- ✅ Synchronous access (no await needed)
- ✅ Fast (dictionary lookup)
- ✅ Explicit control (you decide when to reflect)
- ✅ Predictable (no hidden database queries)
- ✅ Clear error messages guide users

**Usage patterns:**
```python
# Pattern 1: Reflect all, then access
await db.reflect()
users = db.t.users        # Sync, fast
posts = db.t.posts        # Sync, fast

# Pattern 2: Reflect specific table
await db.reflect_table('products')
products = db.t.products  # Sync, fast

# Pattern 3: Created with db.create() (auto-cached)
users = await db.create(User, pk='id')
users = db.t.user         # Works immediately (was cached by create)

# Pattern 4: Multiple table access
users, posts = db.t['user', 'post']
```

### Auto-Caching from db.create()

**When you create a table via `db.create()`:**
```python
users = await db.create(User, pk='id')
```

**This automatically:**
1. Creates the SQLAlchemy Table object
2. Executes CREATE TABLE
3. Wraps in our Table class
4. **Caches in `_tables`** ← Key point!

**Result:** Immediate access via `db.t`
```python
# No reflection needed - was cached by create()
users = db.t.user  # ✅ Works immediately
```

### Reflection Preserves Full Schema

**When reflecting existing tables:**
```python
await db.q("""
    CREATE TABLE products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price REAL DEFAULT 0.0,
        stock INTEGER DEFAULT 0
    )
""")

await db.reflect_table('products')
products = db.t.products

# Full schema preserved
print(products.schema)
# Shows complete CREATE TABLE with all constraints

# Column metadata available
assert products.sa_table.c['id'].primary_key is True
assert products.sa_table.c['name'].nullable is False
assert products.sa_table.c['price'].default is not None
```

### Complete Workflow Examples

**Working with existing database:**
```python
# Connect to existing database
db = Database("sqlite+aiosqlite:///production.db")

# Reflect all existing tables
await db.reflect()

# Access tables dynamically
customers = db.t.customers
orders = db.t.orders
products = db.t.products

# Full CRUD available
customer = await customers.insert({"name": "Alice"})
all_orders = await orders()
product = await products[1]
```

**Mixed workflow (db.create + raw SQL):**
```python
# Create some tables via db.create() (auto-cached)
class User:
    id: int
    name: str

users = await db.create(User, pk='id')

# Create others with raw SQL
await db.q("CREATE TABLE logs (id INT PRIMARY KEY, message TEXT)")
await db.q("CREATE TABLE sessions (id INT PRIMARY KEY, user_id INT)")

# Reflect the raw SQL tables
await db.reflect()

# All accessible now
users = db.t.user       # Was cached by create()
logs = db.t.logs        # Loaded by reflect()
sessions = db.t.sessions  # Loaded by reflect()
```

### Why This Design?

**Advantages:**
1. **Clear separation**: Async operations (reflect) vs sync access (db.t)
2. **Performance**: Cache lookups are instant
3. **Explicit**: No hidden database queries
4. **Helpful**: Error messages guide users to reflect
5. **Flexible**: Reflect all at once or one at a time

**Trade-offs:**
- Requires explicit reflection (can't auto-load on first access)
- User must call `await db.reflect()` or `await db.reflect_table(name)`

---

## 12. Views Support (Phase 7)

Phase 7 adds database views for read-only access to derived data. Views are essentially saved queries that appear as virtual tables.

### Database.create_view() - Create Views

**What it does:**
Creates a database view from a SQL SELECT statement.

**Implementation:**
```python
async def create_view(
    self,
    name: str,
    sql: str,
    replace: bool = False
) -> View:
    """Create a database view."""
    # Drop existing view if replace=True
    if replace:
        async with self._session() as session:
            try:
                await session.execute(sa.text(f"DROP VIEW IF EXISTS {name}"))
            except Exception:
                pass  # View might not exist

    # Create view with raw SQL
    create_sql = f"CREATE VIEW {name} AS {sql}"
    async with self._session() as session:
        await session.execute(sa.text(create_sql))

    # Reflect to get metadata
    view = await self.reflect_view(name)
    return view
```

**Usage:**
```python
# Create view from SELECT
active_users = await db.create_view(
    "active_users",
    "SELECT * FROM user WHERE active = 1"
)

# Replace existing view
active_users = await db.create_view(
    "active_users",
    "SELECT id, name FROM user WHERE active = 1",
    replace=True
)
```

### Database.reflect_view() - Reflect Existing Views

**What it does:**
Reflects an existing view's metadata from the database.

**Implementation:**
```python
async def reflect_view(self, name: str) -> View:
    """Reflect a view from the database."""
    # Check cache
    if name in self._views:
        return self._views[name]

    # Reflect view metadata
    async with self._engine.begin() as conn:
        sa_table = await conn.run_sync(
            lambda sync_conn: sa.Table(
                name,
                self._metadata,
                autoload_with=sync_conn
            )
        )

    # Wrap as View (read-only)
    view = View(name, sa_table, self._engine)
    self._views[name] = view
    return view
```

### View Class - Read-Only Table Wrapper

**Design:**
Views inherit from Table but block write operations.

**Implementation:**
```python
class View(Table):
    """Read-only view wrapper (inherits from Table)."""

    # Read operations inherited (work as-is):
    # - __call__(limit, with_pk)
    # - __getitem__(pk)
    # - lookup(**kwargs)
    # - dataclass()

    # Block write operations:
    async def insert(self, record):
        raise NotImplementedError("Cannot insert into a view")

    async def update(self, record):
        raise NotImplementedError("Cannot update a view")

    async def upsert(self, record):
        raise NotImplementedError("Cannot upsert into a view")

    async def delete(self, pk):
        raise NotImplementedError("Cannot delete from a view")

    # Override xtra() to return View, not Table
    def xtra(self, **filters):
        return View(
            self._name,
            self._sa_table,
            self._engine,
            self._dataclass_cls,
            {**self._xtra_filters, **filters}
        )
```

### ViewAccessor - Dynamic View Access

**Similar to TableAccessor but for views:**

```python
class ViewAccessor:
    def __init__(self, db: Database):
        self._db = db

    def __getattr__(self, name: str) -> View:
        """Access view: db.v.active_users"""
        if name in self._db._views:
            return self._db._views[name]

        raise AttributeError(
            f"View '{name}' not found in cache. "
            f"Use 'await db.create_view()' or 'await db.reflect_view()'."
        )

    def __getitem__(self, key):
        """Access view(s): db.v['active_users'] or db.v['view1', 'view2']"""
        if isinstance(key, str):
            return self.__getattr__(key)
        if isinstance(key, tuple):
            return tuple(self.__getattr__(name) for name in key)
```

**Usage:**
```python
# After creating or reflecting view
active_users = await db.create_view("active_users", "SELECT ...")

# Access via db.v
view = db.v.active_users  # Sync cache access
```

### View Operations

**Read operations work normally:**
```python
view = await db.create_view("user_view", "SELECT * FROM user")

# SELECT all
all_users = await view()

# SELECT with limit
limited = await view(limit=10)

# GET by first column (pseudo-PK)
user = await view[1]  # Uses first column as key

# LOOKUP with WHERE
found = await view.lookup(email="alice@example.com")

# with_pk parameter
results = await view(with_pk=True)
for pk, record in results:
    print(f"PK={pk}: {record}")

# Dataclass support
UserViewDC = view.dataclass()
users = await view()  # Returns dataclass instances
```

**Write operations blocked:**
```python
# All raise NotImplementedError
await view.insert({"name": "Alice"})    # ✗ Blocked
await view.update({"id": 1, ...})       # ✗ Blocked
await view.delete(1)                    # ✗ Blocked
await view.upsert({"id": 1, ...})       # ✗ Blocked
```

### Views as the Solution for JOINs

**Design Decision:** DeeBase intentionally doesn't add a join API. Instead, views serve as the elegant solution for JOIN queries.

**Why views work well for JOINs:**

1. **Schema-less:** Views don't require a Python class - the database provides column metadata during reflection
2. **Full API:** After creating a view with JOIN, you get the full DeeBase API (select, limit, lookup, dataclass, xtra)
3. **Database optimization:** The JOIN is executed by the database, which can optimize it
4. **No N+1:** Getting joined data is a single query, not N+1 FK lookups
5. **SQL is the right tool:** JOINs are a SQL concept; views let you use SQL where it shines

**Use cases:**
- **Repeated joins:** Create a view with `db.create_view()`, use like any table
- **One-off queries:** Use `db.q()` with raw SQL
- **CTEs:** Use `db.q()` with raw SQL

See [Best Practices: Using Views for Joins and CTEs](best-practices.md#using-views-for-joins-and-ctes) for patterns.

### Views with JOIN and Aggregation

**Complex view example:**
```python
# Tables
users = await db.create(User, pk='id')
posts = await db.create(Post, pk='id')

# View with JOIN
posts_with_authors = await db.create_view(
    "posts_with_authors",
    """
    SELECT
        p.id,
        p.title,
        p.views,
        u.name as author_name,
        u.email as author_email
    FROM post p
    JOIN user u ON p.user_id = u.id
    """
)

# Query the derived data
results = await posts_with_authors()
for row in results:
    print(f"{row['title']} by {row['author_name']}")

# Dataclass for type-safe access
PostAuthorDC = posts_with_authors.dataclass()
results = await posts_with_authors()
for post in results:
    print(f"{post.title} by {post.author_name}")
```

### View Lifecycle

**Create → Query → Drop:**
```python
# Create view
view = await db.create_view(
    "temp_view",
    "SELECT * FROM users WHERE created_at > DATE('now', '-7 days')"
)

# Use view
recent_users = await view()

# Drop view
await view.drop()

# View is gone, can create again
view = await db.create_view("temp_view", "SELECT ...")
```

### How Views Work Under the Hood

**Database views are virtual tables:**
1. Store only the SQL query, not the data
2. Execute query each time accessed
3. Reflect as tables (have columns, but no INSERT/UPDATE support)
4. Useful for:
   - Complex joins
   - Filtered data subsets
   - Aggregated data
   - Hiding complexity

**DeeBase View Strategy:**
1. Use SQLAlchemy's reflection to load view metadata
2. Wrap as View (inherits from Table)
3. Block write operations at the DeeBase level
4. All read operations work identically to tables

### Complete Views Example

```python
# Setup tables
class User:
    id: int
    name: str
    status: str

class Order:
    id: int
    user_id: int
    total: float
    status: str

users = await db.create(User, pk='id')
orders = await db.create(Order, pk='id')

# Insert data
await users.insert({"name": "Alice", "status": "active"})
await orders.insert({"user_id": 1, "total": 99.99, "status": "completed"})

# Create views
active_users = await db.create_view(
    "active_users",
    "SELECT * FROM user WHERE status = 'active'"
)

completed_orders = await db.create_view(
    "completed_orders",
    "SELECT * FROM 'order' WHERE status = 'completed'"
)

user_orders = await db.create_view(
    "user_orders",
    """
    SELECT u.name, o.total, o.status
    FROM 'order' o
    JOIN user u ON o.user_id = u.id
    """
)

# Query views
active = await active_users()
completed = await completed_orders()
user_order_data = await user_orders()

# Access via db.v
view = db.v.active_users
results = await view()
```

---

## 13. Transaction Support (Phase 9)

Phase 9 adds explicit transaction support using Python's `contextvars` for thread-safe session tracking in async environments.

### The Transaction Challenge

**Problem:** Each CRUD operation creates its own session and auto-commits:
```python
# Without transactions - each operation commits independently
user = await users.insert({"name": "Alice"})  # Commits
await users.update(user)                       # Commits

# If update fails, insert still committed - partial state!
```

**Solution:** Share a session across multiple operations within a transaction boundary.

### Contextvars for Session Tracking

**What are contextvars?**
- Python feature for context-local state in async code
- Each async task has its own context
- Values don't leak between tasks
- Thread-safe for async operations

**Implementation:**
```python
# In database.py
from contextvars import ContextVar

# Global context variable for tracking active sessions
_session_context: ContextVar[AsyncSession | None] = ContextVar(
    '_session_context',
    default=None
)
```

### Database.transaction() - The Context Manager

**What it does:**
Creates a transaction boundary by managing a shared session in the context.

**Implementation:**
```python
@asynccontextmanager
async def transaction(self):
    """Create a transaction context for multiple operations."""
    # Create a new session for this transaction
    async with self._session_factory() as session:
        # Store session in context
        token = _session_context.set(session)

        try:
            yield session
            # Commit on success
            await session.commit()
        except Exception:
            # Rollback on error
            await session.rollback()
            raise
        finally:
            # Clear context
            _session_context.reset(token)
```

**Key mechanics:**
1. Create session from factory
2. Store in contextvar with `set()` (returns token)
3. Yield session for operations
4. Commit on success, rollback on exception
5. Reset context with token (removes session)

### How CRUD Operations Detect Transactions

**Modified _session_scope() helper:**
```python
@asynccontextmanager
async def _session_scope(self):
    """
    Get a session for an operation.
    If already in a transaction, use that session.
    Otherwise create a new auto-committing session.
    """
    # Check if there's an active transaction
    active_session = _session_context.get()

    if active_session:
        # Inside transaction - use the shared session
        # Don't commit/rollback (transaction handles it)
        yield active_session
    else:
        # No transaction - create new session
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
```

**How it works:**
- `_session_context.get()` retrieves active session (or None)
- If session exists → we're in a transaction → use it
- If no session → create new session with auto-commit
- Operations unchanged - just use `_session_scope()`

### CRUD Operations Participate Automatically

**All operations use _session_scope():**
```python
# In Table.insert()
async def insert(self, record):
    # ... validation ...

    async with self._db._session_scope() as session:
        # Execute INSERT
        result = await session.execute(stmt)
        # ... fetch and return ...

    # If in transaction: session shared, no commit
    # If not in transaction: session auto-commits
```

**The magic:**
- Operations don't know/care if they're in a transaction
- `_session_scope()` handles the logic
- No code changes needed in CRUD methods
- Completely backward compatible

### Transaction Flow Example

```python
# User code
async with db.transaction():
    user = await users.insert({"name": "Alice"})
    await posts.insert({"user_id": user['id']})
```

**What happens internally:**

```
1. db.transaction() called
   ↓
2. Create AsyncSession
   ↓
3. Store in _session_context
   ↓
4. users.insert() called
   ↓
5. _session_scope() checks context → finds session
   ↓
6. Uses shared session, executes INSERT
   ↓
7. Returns without committing (transaction owns commit)
   ↓
8. posts.insert() called
   ↓
9. _session_scope() checks context → finds same session
   ↓
10. Uses same session, executes INSERT
    ↓
11. Returns without committing
    ↓
12. Transaction context exits
    ↓
13. Commits both operations together
    ↓
14. Resets _session_context
```

**If error occurs:**
```
1-10. Same as above
      ↓
11. Exception raised in posts.insert()
    ↓
12. Transaction catches exception
    ↓
13. Rollback both operations
    ↓
14. Resets _session_context
    ↓
15. Re-raises exception
```

### Why Contextvars?

**Thread-safety for async:**
```python
# Task 1
async def task1():
    async with db.transaction():
        await users.insert({"name": "Alice"})

# Task 2
async def task2():
    async with db.transaction():
        await users.insert({"name": "Bob"})

# Run concurrently
await asyncio.gather(task1(), task2())
```

**What happens:**
- Each task has its own context
- Each task gets its own session
- Sessions don't interfere with each other
- `_session_context.get()` returns correct session per task

**Without contextvars:**
- Would need task-local storage (complex)
- Risk of session leakage between tasks
- Not thread-safe

### Commit/Rollback Lifecycle

**Transaction lifecycle:**
```
db.transaction() entered
  ↓
Session created
  ↓
Session stored in context
  ↓
Multiple operations execute (share session)
  ↓
Exception?
  ├─ No → await session.commit()
  └─ Yes → await session.rollback()
  ↓
Context reset
  ↓
Transaction exited
```

**Key points:**
- Commit/rollback happens once per transaction
- All operations in between share the session
- Context automatically cleaned up (finally block)

### Backward Compatibility

**Without transactions (existing code):**
```python
# Each operation gets its own session
user = await users.insert({"name": "Alice"})  # New session, commit
await users.update(user)                       # New session, commit
```

**Flow:**
```
insert() → _session_scope()
         → _session_context.get() → None (no transaction)
         → Create new session
         → Execute INSERT
         → Commit
         → Close session

update() → _session_scope()
         → _session_context.get() → None (no transaction)
         → Create new session
         → Execute UPDATE
         → Commit
         → Close session
```

**With transactions:**
```python
async with db.transaction():
    user = await users.insert({"name": "Alice"})
    await users.update(user)
```

**Flow:**
```
transaction() → Create session
             → Store in _session_context

insert() → _session_scope()
        → _session_context.get() → Session (found!)
        → Use shared session
        → Execute INSERT
        → Return (no commit)

update() → _session_scope()
        → _session_context.get() → Session (found!)
        → Use same session
        → Execute UPDATE
        → Return (no commit)

transaction() exit → Commit shared session
                   → Reset _session_context
```

### Performance Implications

**Without transaction (2 operations):**
- Create session 1
- Execute INSERT
- Commit session 1
- Close session 1
- Create session 2
- Execute UPDATE
- Commit session 2
- Close session 2
- **Total: 2 sessions, 2 commits**

**With transaction (2 operations):**
- Create session
- Execute INSERT
- Execute UPDATE
- Commit session
- Close session
- **Total: 1 session, 1 commit**

**Benefits:**
- Fewer session creations
- Fewer commits (faster)
- Single transaction in database log
- Better atomicity guarantees

### Testing Transactions

**Key test scenarios:**
```python
# Test 1: Basic commit
async with db.transaction():
    user = await users.insert({"name": "Alice"})
    assert await users[user['id']]  # Visible within transaction

# Test 2: Rollback on error
try:
    async with db.transaction():
        user = await users.insert({"name": "Bob"})
        raise ValueError("Oops")
except ValueError:
    pass

# User not in database - rolled back
assert len(await users()) == 0

# Test 3: Nested operations
async with db.transaction():
    user = await users.insert({"name": "Charlie"})
    post = await posts.insert({"user_id": user['id']})
    comment = await comments.insert({"post_id": post['id']})

# All three committed together
```

### Technical Deep Dive: Contextvars

**How `ContextVar` works:**

1. **Creation:**
   ```python
   _session_context: ContextVar[AsyncSession | None] = ContextVar(
       '_session_context',
       default=None
   )
   ```

2. **Setting value:**
   ```python
   token = _session_context.set(session)
   # Returns token for later reset
   # Value stored in current async context
   ```

3. **Getting value:**
   ```python
   active_session = _session_context.get()
   # Returns value for current async context
   # Returns default (None) if not set
   ```

4. **Resetting:**
   ```python
   _session_context.reset(token)
   # Restores previous value (or removes if no previous)
   # Important for cleanup
   ```

**Why tokens?**
- Allow nested context managers
- Restore previous value on reset
- Handle recursive transactions (future feature)

### Future Enhancements

Possible improvements:
1. **Nested transactions** (savepoints)
2. **Transaction isolation levels**
3. **Read-only transactions** (performance optimization)
4. **Transaction context propagation** (across function calls)
5. **Transaction middleware** (logging, metrics)

---

## 14. Foreign Keys & Defaults (Phase 10)

Phase 10 enhances `db.create()` with foreign key constraints and automatic default value extraction using Python's native type system.

### The Design Philosophy

**Problem:** fastlite uses many parameters for create():
```python
# fastlite approach
create(pk='id', foreign_keys=[("user_id", "users")], defaults={"status": "active"})
```

**Solution:** Use Python's native features:
```python
# DeeBase approach - Python's type system
class Post:
    id: int
    author_id: ForeignKey[int, "user"]  # FK via type annotation
    status: str = "draft"                # Default via class attribute
```

### ForeignKey Type Implementation

**What it does:**
Provides a type annotation that encodes foreign key relationships.

**Implementation using Generic and __class_getitem__:**
```python
# In types.py
from typing import TypeVar, Generic

T = TypeVar('T')

class _ForeignKeyType:
    """Internal class holding FK metadata."""
    def __init__(self, base_type: type, table: str, column: str):
        self.base_type = base_type
        self.table = table
        self.column = column

class ForeignKey(Generic[T]):
    """ForeignKey[int, "users"] or ForeignKey[int, "users.id"]"""

    def __class_getitem__(cls, params) -> _ForeignKeyType:
        # params is (int, "users") from ForeignKey[int, "users"]
        if not isinstance(params, tuple) or len(params) != 2:
            raise TypeError("ForeignKey requires two parameters: ForeignKey[type, 'table']")

        base_type, reference = params

        # Parse "table.column" or just "table" (default to 'id')
        if '.' in reference:
            table, column = reference.rsplit('.', 1)
        else:
            table, column = reference, 'id'

        return _ForeignKeyType(base_type, table, column)
```

**How `__class_getitem__` works:**
- Called when you write `ForeignKey[int, "users"]`
- Receives the bracket contents as a tuple `(int, "users")`
- Returns our custom `_ForeignKeyType` object
- This object is stored in the class's `__annotations__`

**Usage patterns:**
```python
# Reference user.id (default column)
author_id: ForeignKey[int, "user"]

# Reference user.uuid explicitly
author_uuid: ForeignKey[str, "user.uuid"]
```

### Detecting ForeignKey in db.create()

**How we check if a type is a ForeignKey:**
```python
# In database.py create() method
from .types import _ForeignKeyType

for field_name, field_type in annotations.items():
    # Check if it's a ForeignKey annotation
    if isinstance(field_type, _ForeignKeyType):
        # Extract FK metadata
        fk_base_type = field_type.base_type  # int
        fk_table = field_type.table          # "user"
        fk_column = field_type.column        # "id"

        # Use base type for column definition
        sa_type = python_type_to_sqlalchemy(fk_base_type)

        # Store FK info for constraint generation
        foreign_keys.append((field_name, fk_table, fk_column))
    else:
        # Normal type handling
        sa_type = python_type_to_sqlalchemy(field_type)
```

### SQLAlchemy ForeignKeyConstraint Generation

**Building FK constraints:**
```python
from sqlalchemy import ForeignKeyConstraint

# After creating columns, add FK constraints
constraints = []
for local_col, ref_table, ref_col in foreign_keys:
    fk = ForeignKeyConstraint(
        [local_col],                    # Local column(s)
        [f"{ref_table}.{ref_col}"]      # Reference "table.column"
    )
    constraints.append(fk)

# Create table with constraints
sa_table = sa.Table(
    table_name,
    self._metadata,
    *columns,
    *constraints  # Add FK constraints
)
```

**Generated SQL:**
```sql
CREATE TABLE post (
    id INTEGER NOT NULL,
    title VARCHAR NOT NULL,
    author_id INTEGER NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(author_id) REFERENCES user (id)
)
```

### Default Value Extraction

**What it does:**
Extracts scalar default values from class definitions for SQL DEFAULT clauses.

**Implementation:**
```python
# In dataclass_utils.py
from dataclasses import is_dataclass, fields, MISSING as DC_MISSING

MISSING = object()  # Sentinel for "no default"

def extract_defaults(cls: type) -> dict[str, Any]:
    """Extract scalar defaults from class (regular or dataclass)."""
    defaults = {}

    if is_dataclass(cls):
        # Handle @dataclass
        for f in fields(cls):
            if f.default is not DC_MISSING:
                # Only extract immutable scalars
                if isinstance(f.default, (str, int, float, bool)):
                    defaults[f.name] = f.default
            # Note: default_factory is intentionally skipped
    else:
        # Handle regular class
        for name in cls.__annotations__:
            value = getattr(cls, name, MISSING)
            if value is not MISSING:
                # Only extract immutable scalars
                if isinstance(value, (str, int, float, bool)):
                    defaults[name] = value

    return defaults
```

**Why only scalar types?**
- `str`, `int`, `float`, `bool` can be directly translated to SQL defaults
- Mutable types (`dict`, `list`) would share state between rows
- `default_factory` is runtime behavior, not a SQL concept

**Example:**
```python
class Article:
    id: int
    status: str = "draft"      # Extracted: SQL DEFAULT 'draft'
    views: int = 0             # Extracted: SQL DEFAULT 0
    featured: bool = False     # Extracted: SQL DEFAULT 0
    metadata: dict = {}        # Skipped: mutable default
```

### SQLAlchemy server_default for SQL DEFAULTs

**How defaults become SQL:**
```python
from sqlalchemy import Column, Integer, String, text

# In db.create() - when building columns
defaults = extract_defaults(cls)

for field_name, field_type in annotations.items():
    # ... type handling ...

    # Check for default value
    server_default = None
    if field_name in defaults:
        value = defaults[field_name]
        if isinstance(value, str):
            server_default = f"'{value}'"  # Quote strings
        elif isinstance(value, bool):
            server_default = "1" if value else "0"  # SQLite boolean
        else:
            server_default = str(value)  # Numbers as-is

    col = sa.Column(
        field_name,
        sa_type,
        primary_key=is_pk,
        nullable=nullable,
        server_default=sa.text(server_default) if server_default else None
    )
```

**Generated SQL:**
```sql
CREATE TABLE article (
    id INTEGER NOT NULL,
    status VARCHAR DEFAULT 'draft',
    views INTEGER DEFAULT 0,
    featured BOOLEAN DEFAULT 0,
    PRIMARY KEY (id)
)
```

### if_not_exists Implementation

**Challenge:** SQLAlchemy's table creation doesn't automatically handle "if not exists".

**Solution:** Use `CreateTable` with `if_not_exists=True` and handle metadata collision.

**Implementation:**
```python
async def create(
    self,
    cls: type,
    pk: str | list[str] | None = None,
    if_not_exists: bool = False,
    replace: bool = False,
) -> Table:
    table_name = cls.__name__.lower()

    # Handle existing table in metadata
    if table_name in self._metadata.tables:
        if replace:
            # Drop existing table first
            existing = self._metadata.tables[table_name]
            async with self._session() as session:
                await session.execute(sa.schema.DropTable(existing))
            self._metadata.remove(existing)
        elif if_not_exists:
            # Return existing table wrapper
            if table_name in self._tables:
                return self._tables[table_name]
        else:
            # Error: table already in metadata
            raise SchemaError(f"Table {table_name} already exists in metadata")

    # Build table schema...
    sa_table = sa.Table(table_name, self._metadata, *columns, *constraints)

    # Execute CREATE TABLE
    async with self._session() as session:
        create_stmt = sa.schema.CreateTable(sa_table, if_not_exists=if_not_exists)
        await session.execute(create_stmt)
```

**Key insight:** Two levels of "exists":
1. **Metadata level** - Table object in SQLAlchemy's registry
2. **Database level** - Actual table in database

**if_not_exists=True:**
- Check metadata first → return cached if exists
- Use `CreateTable(..., if_not_exists=True)` for database level
- Safely handles both levels

### replace Implementation

**What it does:**
Drops existing table and recreates it fresh.

**Implementation:**
```python
if replace:
    # Check if table exists in metadata
    if table_name in self._metadata.tables:
        existing = self._metadata.tables[table_name]

        # Drop from database
        async with self._session() as session:
            await session.execute(sa.schema.DropTable(existing))

        # Remove from metadata (important!)
        self._metadata.remove(existing)

    # Remove from our cache
    if table_name in self._tables:
        del self._tables[table_name]
```

**Why remove from metadata?**
- SQLAlchemy doesn't allow two tables with same name in metadata
- `metadata.remove(table)` clears the registry
- Allows creating new table with same name

### Complete create() Flow with Phase 10

```python
# User code
class Post:
    id: int
    title: str
    author_id: ForeignKey[int, "user"]
    status: str = "draft"
    views: int = 0

posts = await db.create(Post, pk='id', if_not_exists=True)
```

**Internal flow:**

```
1. Extract annotations
   ↓
2. Detect ForeignKey types
   author_id → _ForeignKeyType(int, "user", "id")
   ↓
3. Extract defaults
   {"status": "draft", "views": 0}
   ↓
4. Build columns with server_default
   sa.Column('status', sa.String, server_default=text("'draft'"))
   sa.Column('views', sa.Integer, server_default=text("0"))
   ↓
5. Build FK constraints
   ForeignKeyConstraint(['author_id'], ['user.id'])
   ↓
6. Create sa.Table with columns + constraints
   ↓
7. Check if_not_exists for metadata collision
   ↓
8. Execute CreateTable(sa_table, if_not_exists=True)
   ↓
9. Wrap and cache Table
```

**Generated SQL:**
```sql
CREATE TABLE IF NOT EXISTS post (
    id INTEGER NOT NULL,
    title VARCHAR NOT NULL,
    author_id INTEGER NOT NULL,
    status VARCHAR DEFAULT 'draft',
    views INTEGER DEFAULT 0,
    PRIMARY KEY (id),
    FOREIGN KEY(author_id) REFERENCES user (id)
)
```

### Class vs Dataclass Behavior

**Regular class → dict outputs:**
```python
class User:
    id: int
    name: str
    status: str = "active"

users = await db.create(User, pk='id')
user = await users.insert({"name": "Alice"})
print(type(user))  # dict
print(user["status"])  # "active" (from SQL default)
```

**@dataclass → dataclass outputs:**
```python
@dataclass
class User:
    id: Optional[int] = None
    name: str = ""
    status: str = "active"

users = await db.create(User, pk='id')
user = await users.insert({"name": "Alice"})
print(type(user))  # User
print(user.status)  # "active" (from SQL default)
```

**Key insight:** The `@dataclass` decorator determines output type, not the defaults.

### Error Handling

**FK constraint violation:**
```python
from deebase import IntegrityError

try:
    await posts.insert({"title": "Hello", "author_id": 999})  # No user 999
except IntegrityError as e:
    print(f"FK violated: {e.constraint}")
```

**Schema collision:**
```python
from deebase import SchemaError

# Without if_not_exists
users = await db.create(User, pk='id')
users = await db.create(User, pk='id')  # SchemaError!

# With if_not_exists
users = await db.create(User, pk='id', if_not_exists=True)  # OK
```

### Performance Notes

**Defaults:**
- `extract_defaults()` runs once at table creation
- SQL DEFAULT computed by database, not Python
- No runtime overhead for defaults

**Foreign keys:**
- FK constraints checked by database on INSERT/UPDATE
- No Python-side validation (database handles it)
- FK enforcement must be enabled in SQLite: `PRAGMA foreign_keys = ON`

**if_not_exists:**
- Single CREATE TABLE query
- No separate "check if exists" query
- Database handles the IF NOT EXISTS logic

---

## 11. FK Navigation Implementation (Phase 11)

Phase 11 adds foreign key navigation - the ability to traverse relationships between tables.

### Architecture

```
posts.fk.author_id(post)  # Convenience API
        │
        ▼
    FKAccessor             # Handles attribute access
        │
        ▼
table.get_parent()         # Power user API
        │
        ▼
    _foreign_keys          # FK metadata list
        │
        ▼
    parent_table[fk_value] # Standard Table.__getitem__
```

### FK Metadata Storage

FK metadata is stored on each Table instance:

```python
# In Table.__init__
self._foreign_keys = foreign_keys or []

# Format: list of dicts
# [{'column': 'author_id', 'references': 'user.id'}, ...]
```

**Source of FK metadata:**
1. **From `db.create()`**: Parsed from `ForeignKey[T, "table"]` annotations
2. **From reflection**: Extracted from SQLAlchemy's FK inspection

```python
# In Database._extract_fk_metadata()
def _extract_fk_metadata(self, sa_table: sa.Table) -> list[dict]:
    fk_metadata = []
    for fk in sa_table.foreign_keys:
        local_col = fk.parent.name
        ref_full = fk.target_fullname  # "table.column"
        fk_metadata.append({
            'column': local_col,
            'references': ref_full
        })
    return fk_metadata
```

### FKAccessor Class

The convenience API uses Python's `__getattr__` for clean syntax:

```python
class FKAccessor:
    def __init__(self, table: "Table"):
        self._table = table

    def __getattr__(self, fk_column: str):
        """Return callable for navigation."""
        async def navigate(record: dict | Any) -> dict | Any | None:
            return await self._table.get_parent(record, fk_column)
        return navigate
```

**Key insight:** `__getattr__` returns an async function (not awaitable directly), which is then called with the record.

```python
# User writes:
author = await posts.fk.author_id(post)

# Becomes:
accessor = posts.fk
navigate_func = accessor.__getattr__("author_id")
author = await navigate_func(post)
```

### get_parent() Implementation

The core navigation logic:

```python
async def get_parent(self, record, fk_column):
    # 1. Convert record to dict
    data = self._from_input(record)

    # 2. Validate FK column exists
    if fk_column not in self._sa_table.c:
        raise ValidationError(...)

    # 3. Find FK definition
    fk_def = None
    for fk in self._foreign_keys:
        if fk['column'] == fk_column:
            fk_def = fk
            break

    if fk_def is None:
        raise ValidationError(f"'{fk_column}' is not a foreign key")

    # 4. Get FK value
    fk_value = data.get(fk_column)
    if fk_value is None:
        return None  # Nullable FK

    # 5. Parse reference (e.g., "user.id")
    ref_parts = fk_def['references'].split('.')
    ref_table = ref_parts[0]

    # 6. Get parent table from cache
    parent_table = self._db._get_table(ref_table)
    if parent_table is None:
        raise SchemaError(f"Referenced table '{ref_table}' not found")

    # 7. Fetch parent record
    try:
        return await parent_table[fk_value]
    except NotFoundError:
        return None  # Dangling FK
```

### get_children() Implementation

Reverse navigation queries the child table:

```python
async def get_children(self, record, child_table, fk_column):
    # 1. Extract PK from record
    data = self._from_input(record)
    pk_value = data.get(pk_col.name)

    # 2. Resolve child table (string or Table)
    if isinstance(child_table, str):
        resolved_table = self._db._get_table(child_table)
    else:
        resolved_table = child_table

    # 3. Query child table
    async with resolved_table._session_scope() as (session, should_manage):
        stmt = sa.select(resolved_table._sa_table).where(
            resolved_table._sa_table.c[fk_column] == pk_value
        )
        result = await session.execute(stmt)
        rows = result.fetchall()
        return [resolved_table._to_record(row) for row in rows]
```

### Database Reference

Navigation requires access to other tables via `_db` reference:

```python
# In Table.__init__
self._db = db  # Reference to Database instance

# In Database.create()
table_instance = Table(
    table_name, sa_table, self._engine,
    dataclass_cls=cls,
    db=self,  # Pass reference
    foreign_keys=fk_metadata,
)
```

### Return Type Handling

Navigation respects the target table's dataclass setting:

```python
# In get_parent()
return await parent_table[fk_value]

# parent_table[fk_value] uses parent's _to_record()
# which returns dict or dataclass based on parent's _dataclass_cls
```

### Why Not ORM-Style `post.author`?

We chose explicit navigation (`posts.fk.author_id(post)`) over implicit (`post.author`) because:

1. **Async requirement**: Python attribute access is synchronous
2. **No session tracking**: Our records are plain dicts/dataclasses, not ORM-managed objects
3. **Explicit is better**: Clear what triggers a database query
4. **No N+1 by accident**: Users must consciously navigate

### Performance Considerations

**Single record navigation:** O(1) database query per navigation
```python
author = await posts.fk.author_id(post)  # 1 query
```

**Bulk navigation:** Use JOINs instead of N+1
```python
# ❌ N queries
for post in posts:
    author = await posts_table.fk.author_id(post)

# ✅ 1 query with JOIN
results = await db.q("""
    SELECT p.*, u.name as author_name
    FROM post p JOIN user u ON p.author_id = u.id
""")
```

---

## 15. Index Support (Phase 12)

Phase 12 adds explicit index support for query optimization using SQLAlchemy's Index class.

### Index Class Implementation

**What it does:**
Provides a clean way to define named indexes with optional uniqueness constraints.

**Implementation:**
```python
# In types.py
class Index:
    """Named index definition for table creation."""

    def __init__(self, name: str, *columns: str, unique: bool = False):
        if not columns:
            raise ValueError("Index requires at least one column")
        self.name = name
        self.columns = list(columns)
        self.unique = unique
```

**Key features:**
- Takes variable number of column names (`*columns`)
- Optional `unique=True` for unique constraints
- Simple data class to hold index metadata

### Index Specification Options

**Three syntaxes in `db.create()`:**

```python
indexes=[
    "slug",                                    # String: auto-named
    ("author_id", "created_at"),               # Tuple: composite, auto-named
    Index("idx_title", "title", unique=True),  # Index: named with options
]
```

**Processing logic:**
```python
# In Database._create_indexes()
for idx_spec in indexes:
    if isinstance(idx_spec, str):
        # Single column, auto-generated name
        columns = [idx_spec]
        name = f"ix_{table_name}_{idx_spec}"
        unique = False
    elif isinstance(idx_spec, tuple):
        # Composite index, auto-generated name
        columns = list(idx_spec)
        name = f"ix_{table_name}_{'_'.join(columns)}"
        unique = False
    elif isinstance(idx_spec, Index):
        # Named index with options
        columns = idx_spec.columns
        name = idx_spec.name
        unique = idx_spec.unique
```

### SQLAlchemy Index Creation

**Building and executing indexes:**
```python
from sqlalchemy import Index as SAIndex
from sqlalchemy.schema import CreateIndex

# Get SQLAlchemy column objects
sa_columns = [sa_table.c[col_name] for col_name in columns]

# Create SQLAlchemy Index object
sa_index = SAIndex(name, *sa_columns, unique=unique)

# Execute CREATE INDEX
async with self._session() as session:
    await session.execute(CreateIndex(sa_index))
```

**Generated SQL:**
```sql
CREATE INDEX ix_article_slug ON article (slug)
CREATE INDEX ix_article_author_id_created_at ON article (author_id, created_at)
CREATE UNIQUE INDEX idx_title ON article (title)
```

### table.create_index() Implementation

**Adding indexes after table creation:**
```python
async def create_index(
    self,
    columns: str | list[str],
    name: str = None,
    unique: bool = False
) -> None:
    # Normalize to list
    if isinstance(columns, str):
        columns = [columns]

    # Validate columns exist
    for col_name in columns:
        if col_name not in self._sa_table.c:
            raise ValidationError(f"Column '{col_name}' not found")

    # Auto-generate name if needed
    if name is None:
        name = f"ix_{self._name}_{'_'.join(columns)}"

    # Get column objects
    sa_columns = [self._sa_table.c[col_name] for col_name in columns]

    # Create and execute
    sa_index = SAIndex(name, *sa_columns, unique=unique)
    async with self._session_scope() as (session, should_manage):
        await session.execute(CreateIndex(sa_index))
        if should_manage:
            await session.commit()
```

### table.drop_index() Implementation

**Removing indexes:**
```python
async def drop_index(self, name: str) -> None:
    async with self._session_scope() as (session, should_manage):
        # Use raw SQL for DROP INDEX
        await session.execute(sa.text(f"DROP INDEX {name}"))
        if should_manage:
            await session.commit()
```

**Why raw SQL?**
SQLAlchemy doesn't have a direct `DropIndex` DDL construct like `CreateIndex`. Using `sa.text()` works across both SQLite and PostgreSQL.

### table.indexes Property

**Listing indexes from SQLAlchemy metadata:**
```python
@property
def indexes(self) -> list[dict]:
    result = []
    for index in self._sa_table.indexes:
        result.append({
            'name': index.name,
            'columns': [col.name for col in index.columns],
            'unique': index.unique
        })
    return result
```

**Key insight:** SQLAlchemy's `Table.indexes` attribute tracks all indexes created via `SAIndex`. This works because indexes created with `CreateIndex` are automatically registered with the table metadata.

### Index Auto-Naming Convention

**Pattern:** `ix_{tablename}_{column1}_{column2}...`

Examples:
| Index Specification | Generated Name |
|---------------------|----------------|
| `"title"` | `ix_article_title` |
| `("author_id", "created_at")` | `ix_article_author_id_created_at` |
| `Index("custom", "col")` | `custom` (uses provided name) |

### Unique Index Enforcement

**How unique indexes work:**
```python
# Create unique index
await users.create_index("email", unique=True)

# Insert first user
await users.insert({"id": 1, "email": "alice@example.com"})

# Duplicate raises IntegrityError
try:
    await users.insert({"id": 2, "email": "alice@example.com"})
except IntegrityError:
    print("Email already exists")
```

**Database enforces uniqueness:**
- SQLite: `UNIQUE constraint failed`
- PostgreSQL: `duplicate key value violates unique constraint`

DeeBase catches these and re-raises as `IntegrityError`.

### Why Not Auto-Create Indexes?

**Design decision:** Indexes are opt-in, not automatic.

**Reasoning:**
1. **Write performance**: Indexes slow down INSERT/UPDATE/DELETE
2. **Storage**: Indexes consume disk space
3. **Choice**: Developers should choose what to index based on query patterns
4. **FK columns**: Even FK columns aren't auto-indexed (database-specific behavior)

### Performance Considerations

**Index trade-offs:**
| Operation | With Index | Without Index |
|-----------|------------|---------------|
| SELECT WHERE | O(log n) | O(n) |
| INSERT | Slower (update index) | Faster |
| UPDATE | Slower if indexed col | Normal |
| DELETE | Slower (update index) | Normal |

**Best practices:**
- Index columns used in WHERE clauses
- Index columns used in ORDER BY
- Index FK columns for JOIN performance
- Don't over-index (measure actual queries)

### Complete Index Flow

```python
# User code
class Article:
    id: int
    title: str
    slug: str

articles = await db.create(
    Article,
    pk='id',
    indexes=[
        Index("idx_slug", "slug", unique=True),
        "title"
    ]
)
```

**Internal flow:**
```
1. db.create() builds table
   ↓
2. Table created in database
   ↓
3. _create_indexes() called with indexes list
   ↓
4. For each index spec:
   ├─ Parse specification (str/tuple/Index)
   ├─ Validate columns exist
   ├─ Build SAIndex object
   └─ Execute CreateIndex
   ↓
5. Return Table (indexes now exist in DB)
```

**Generated SQL:**
```sql
CREATE TABLE article (
    id INTEGER NOT NULL,
    title VARCHAR NOT NULL,
    slug VARCHAR NOT NULL,
    PRIMARY KEY (id)
);
CREATE UNIQUE INDEX idx_slug ON article (slug);
CREATE INDEX ix_article_title ON article (title);
```

---

## Key Takeaways

1. **SQLAlchemy Core, Not ORM**: We use Tables and Columns directly, not ORM models
2. **Async Throughout**: AsyncEngine, AsyncSession, async operations
3. **Type Safety**: Python types → SQLAlchemy types → Database SQL
4. **Dialect Agnostic**: Same code works for SQLite and PostgreSQL via dialects
5. **Wrapper Pattern**: We wrap SQLAlchemy objects (Table, Column, View) with our own classes
6. **Metadata Registry**: MetaData tracks all table definitions
7. **Session Per Operation**: Each operation gets its own session with auto-commit
8. **Compile for SQL**: Use `.compile(engine)` to generate database-specific SQL
9. **Explicit Reflection**: Tables/views must be explicitly reflected before dynamic access
10. **Read-Only Views**: Views inherit from Table but block write operations
11. **Opt-In Type Safety**: Start with dicts, add dataclasses when needed
12. **Foreign Keys via Type Annotations**: `ForeignKey[T, "table"]` encodes relationships in Python's type system
13. **Defaults from Class Definitions**: Scalar class defaults become SQL DEFAULT clauses via `server_default`

## Further Reading

- [SQLAlchemy Core Documentation](https://docs.sqlalchemy.org/en/20/core/)
- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [SQLAlchemy Type System](https://docs.sqlalchemy.org/en/20/core/types.html)
- [SQLAlchemy Dialects](https://docs.sqlalchemy.org/en/20/dialects/)
- [SQLAlchemy Reflection](https://docs.sqlalchemy.org/en/20/core/reflection.html)
