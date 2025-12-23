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
