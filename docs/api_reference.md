# DeeBase API Reference

Complete API reference for DeeBase async database library.

## Table of Contents

- [Database](#database)
- [Table](#table)
- [View](#view)
- [Column & ColumnAccessor](#column--columnaccessor)
- [Types](#types)
- [Exceptions](#exceptions)
- [Utilities](#utilities)
- [API Module (FastAPI Integration)](#api-module-fastapi-integration)
- [Validation Module](#validation-module)

---

## Database

The main entry point for database operations.

### Constructor

```python
Database(url: str)
```

Create a new database connection.

**Parameters:**
- `url` (str): Database URL
  - SQLite: `"sqlite+aiosqlite:///myapp.db"` or `"sqlite+aiosqlite:///:memory:"`
  - PostgreSQL: `"postgresql+asyncpg://user:pass@localhost/dbname"`

**Example:**
```python
from deebase import Database

db = Database("sqlite+aiosqlite:///myapp.db")
```

### Properties

#### `db.engine`

Access the underlying SQLAlchemy `AsyncEngine`.

**Returns:** `AsyncEngine`

#### `db.t`

Dynamic table accessor for accessing cached tables.

**Returns:** `TableAccessor`

**Example:**
```python
users = db.t.users  # Access cached 'users' table
```

#### `db.v`

Dynamic view accessor for accessing cached views.

**Returns:** `ViewAccessor`

**Example:**
```python
active_users = db.v.active_users  # Access cached view
```

### Methods

#### `async db.q(query: str) -> list[dict]`

Execute raw SQL and return results as dictionaries.

**When to use:**
- Complex queries not easily expressed with the Table API
- Database-specific features (CTEs, window functions, etc.)
- Bulk operations for performance
- Schema modifications (ALTER TABLE, CREATE INDEX, etc.)
- Working with databases before reflecting tables

**When NOT to use:**
- Simple CRUD operations (use Table methods instead)
- When you want type safety (use dataclass-based Table operations)

**Parameters:**
- `query` (str): SQL query string

**Returns:** `list[dict]` - List of result rows (empty for DDL/DML)

**Raises:**
- `ConnectionError`: Database connection failed
- `SchemaError`: SQL syntax error or table not found
- `RuntimeError`: Unexpected error

**Example:**
```python
# Query
results = await db.q("SELECT * FROM users WHERE age > 18")

# DDL
await db.q("CREATE TABLE products (id INT PRIMARY KEY, name TEXT)")

# DML
await db.q("INSERT INTO products (id, name) VALUES (1, 'Widget')")
```

#### `async db.create(cls: type, pk: str | list[str] = None, if_not_exists: bool = False, replace: bool = False, indexes: list = None) -> Table`

Create a table from a Python class with type annotations.

**When to use:**
- Starting a new project with schema defined in Python
- When you want type-safe schema definitions
- When the schema is version-controlled in Python code
- When you need foreign key relationships between tables
- Simple to moderate schema complexity

**When NOT to use:**
- Need advanced SQL features (CHECK constraints, triggers, custom types)
- Working with an existing database (use `db.reflect()` instead)
- Complex database-specific constraints

**Parameters:**
- `cls` (type): Class with type annotations defining schema
- `pk` (str | list[str], optional): Primary key column name(s). Defaults to `'id'`.
- `if_not_exists` (bool, optional): Don't error if table already exists. Defaults to `False`.
- `replace` (bool, optional): Drop existing table before creating. Defaults to `False`.
- `indexes` (list, optional): List of indexes to create. Each item can be:
  - `str`: Single column index with auto-generated name (e.g., `"slug"`)
  - `tuple`: Composite index with auto-generated name (e.g., `("author_id", "created_at")`)
  - `Index`: Named index with options (e.g., `Index("idx_email", "email", unique=True)`)

**Returns:** `Table` - Table instance

**Raises:**
- `ValidationError`: Class has no type annotations, or index column not found
- `SchemaError`: Primary key column not found in annotations, or table already exists

**Features:**
- **Default values**: Class attributes with defaults become SQL `DEFAULT` values
- **Foreign keys**: Use `ForeignKey[type, "table"]` type annotation
- **Nullable**: Use `Optional[T]` for nullable columns
- **Indexes**: Use `indexes` parameter with strings, tuples, or `Index` objects

**Example:**
```python
from deebase import Database, ForeignKey, Index, Text

# Basic table with defaults
class User:
    id: int
    name: str
    email: str
    status: str = "active"  # SQL DEFAULT 'active'
    login_count: int = 0    # SQL DEFAULT 0

users = await db.create(User, pk='id')

# Table with foreign key and indexes
class Post:
    id: int
    title: str
    slug: str
    content: Text
    author_id: ForeignKey[int, "user"]  # FK to user.id
    created_at: str

posts = await db.create(
    Post,
    pk='id',
    indexes=[
        "slug",                                    # Simple index
        ("author_id", "created_at"),               # Composite index
        Index("idx_title_unique", "title", unique=True),  # Named unique index
    ]
)

# Safe creation (no error if exists)
users = await db.create(User, pk='id', if_not_exists=True)

# Drop and recreate
users = await db.create(User, pk='id', replace=True)

# Composite primary key
class OrderItem:
    order_id: int
    product_id: int
    quantity: int

order_items = await db.create(OrderItem, pk=['order_id', 'product_id'])
```

#### `async db.reflect(schema: str = None) -> None`

Reflect all tables from the database into cache.

**When to use:**
- Connecting to an existing database with many tables
- Database created by migrations or external tools
- At application startup for existing databases
- When you need to work with all tables at once

**When NOT to use:**
- Tables created with `db.create()` (already cached automatically)
- When you only need one specific table (use `db.reflect_table()` instead)
- On every request (expensive operation - do once at startup)

**Parameters:**
- `schema` (str, optional): Schema name for databases that support schemas

**Example:**
```python
await db.reflect()
users = db.t.users  # Now available
posts = db.t.posts  # Now available
```

#### `async db.reflect_table(name: str) -> Table`

Reflect a specific table from the database.

**When to use:**
- Table created with raw SQL (`db.q("CREATE TABLE...")`)
- Table created by migration tool or external application
- When you only need one specific table (more efficient than `db.reflect()`)
- After manually creating a table with `db.q()`

**When NOT to use:**
- Table created with `db.create()` (already cached automatically)
- When you need multiple tables (use `db.reflect()` for bulk reflection)

**Parameters:**
- `name` (str): Table name to reflect

**Returns:** `Table` - Reflected table instance

**Example:**
```python
products = await db.reflect_table('products')
# Also makes db.t.products available
```

#### `async db.create_view(name: str, sql: str, replace: bool = False) -> View`

Create a database view.

**When to use:**
- Creating views from within your application
- Views that are part of your application logic
- When you want the view definition in Python code
- New views that don't exist yet

**When NOT to use:**
- View already exists in database (use `db.reflect_view()` instead)
- Views created by migration tools (reflect them instead)

**Note:** After `db.create_view()`, the view is **automatically cached** and immediately available via `db.v.viewname`. No reflection needed.

**Parameters:**
- `name` (str): View name
- `sql` (str): SQL query defining the view
- `replace` (bool, optional): Replace if exists. Defaults to False.

**Returns:** `View` - View instance

**Example:**
```python
view = await db.create_view(
    "active_users",
    "SELECT * FROM users WHERE active = 1"
)
```

#### `async db.reflect_view(name: str) -> View`

Reflect an existing view from the database.

**When to use:**
- View created with raw SQL (`db.q("CREATE VIEW...")`)
- View created by migration tools or external applications
- Views that exist in the database but weren't created via `db.create_view()`
- After manually creating a view with `db.q()`

**Key insight for JOINs:** Views are the recommended way to handle JOIN queries in DeeBase. Create a view with a JOIN query, then use it like any table:

```python
# Create view with JOIN (one-time)
await db.create_view("post_authors", """
    SELECT p.id, p.title, u.name as author_name
    FROM posts p JOIN users u ON p.author_id = u.id
""")

# Use like any table - no Python class needed!
results = await db.v.post_authors()           # All rows
limited = await db.v.post_authors(limit=10)   # With limit
found = await db.v.post_authors.lookup(author_name="Alice")
PostAuthorDC = db.v.post_authors.dataclass()  # Type-safe access!
```

The database provides column metadata during reflection, so you get the full DeeBase API without defining a Python schema. See [Best Practices: Using Views for Joins and CTEs](best-practices.md#using-views-for-joins-and-ctes) for more patterns.

**When NOT to use:**
- View created with `db.create_view()` (already cached automatically)

**Note:** Only views created **outside** DeeBase need reflection. Views created with `db.create_view()` are automatically cached.

**Parameters:**
- `name` (str): View name to reflect

**Returns:** `View` - Reflected view instance

**Example:**
```python
view = await db.reflect_view('active_users')
# Also makes db.v.active_users available
```

#### `async db.transaction() -> AsyncContextManager`

Create a transaction context for multi-operation atomicity.

**When to use:**
- Multiple operations must succeed or fail together (atomicity)
- Money transfers, inventory moves, or data synchronization
- Creating related records across multiple tables
- Batch operations where partial success is unacceptable
- Read-modify-write operations to prevent race conditions

**When NOT to use:**
- Single operations (each operation is already atomic)
- Read-only queries (no benefit from transactions)
- DDL operations (CREATE TABLE, ALTER TABLE - not transactional in most databases)
- Long-running operations (hold locks minimally)

**Parameters:**
- Yields: `AsyncSession` - SQLAlchemy async session

**Returns:** Context manager that commits on success, rolls back on exception

**Usage example:**
```python
# Money transfer (atomic)
async with db.transaction():
    sender = await users[1]
    receiver = await users[2]

    sender['balance'] -= 100.0
    receiver['balance'] += 100.0

    await users.update(sender)
    await users.update(receiver)
# Both updates commit together

# Rollback on error
async with db.transaction():
    user = await users.insert({"name": "Alice"})
    # Error here rolls back the insert
    await posts.insert({"user_id": 9999})  # Fails - user insert rolled back
```

**Related operations:**
- All Table CRUD operations (insert, update, delete) participate automatically
- No code changes needed - operations detect active transaction
- Backward compatible - existing code works without transactions

#### `async db.enable_foreign_keys() -> None`

Enable foreign key enforcement on SQLite databases.

**When to use:**
- After creating a SQLite database connection that uses foreign keys
- At the start of your application initialization
- Safe to call on any database (no-op on PostgreSQL)

**Why it exists:**
SQLite has foreign key enforcement disabled by default for backward compatibility.
PostgreSQL always enforces foreign keys. This method provides a portable way to
ensure FK constraints are enforced.

**Example:**
```python
db = Database("sqlite+aiosqlite:///app.db")
await db.enable_foreign_keys()

# Now foreign key constraints are enforced
await db.q("CREATE TABLE users (id INTEGER PRIMARY KEY)")
await db.q("CREATE TABLE posts (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id))")

# This will fail with IntegrityError (FK violation)
await db.q("INSERT INTO posts (user_id) VALUES (999)")
```

**Notes:**
- Must be called after connection, before FK operations
- Safe to call multiple times
- No effect on PostgreSQL (always enforces FKs)

#### `async db.close() -> None`

Close the database connection and dispose of the engine.

**Example:**
```python
await db.close()
```

### Context Manager

Database can be used as an async context manager:

```python
async with Database("sqlite+aiosqlite:///myapp.db") as db:
    users = await db.create(User, pk='id')
    await users.insert({"name": "Alice"})
# Automatically closed on exit
```

---

## Table

Represents a database table with CRUD operations.

### Properties

#### `table.c`

Access table columns.

**Returns:** `ColumnAccessor`

**Example:**
```python
users.c.name  # Access 'name' column
```

#### `table.schema`

Get the SQL schema definition.

**Returns:** `str` - CREATE TABLE SQL

**Example:**
```python
print(users.schema)
# CREATE TABLE users (
#     id INTEGER NOT NULL,
#     name VARCHAR,
#     PRIMARY KEY (id)
# )
```

#### `table.sa_table`

Access the underlying SQLAlchemy Table object.

**Returns:** `sqlalchemy.Table`

#### `table.foreign_keys`

List of foreign key definitions for this table.

**Returns:** `list[dict]` - List of FK definitions: `[{'column': str, 'references': 'table.column'}, ...]`

**Example:**
```python
print(posts.foreign_keys)
# [{'column': 'author_id', 'references': 'users.id'},
#  {'column': 'category_id', 'references': 'categories.id'}]
```

#### `table.fk`

Access foreign key navigation. Provides clean syntax for following foreign keys.

**Returns:** `FKAccessor`

**Example:**
```python
# Navigate from post to author via FK
post = await posts[1]
author = await posts.fk.author_id(post)  # Returns author record or None
```

See [get_parent()](#async-tableget_parentrecord-fk_column---dict--any--none) for the power user API.

#### `table.indexes`

List of indexes on this table.

**Returns:** `list[dict]` - List of index definitions: `[{'name': str, 'columns': [str], 'unique': bool}, ...]`

**Example:**
```python
print(posts.indexes)
# [{'name': 'ix_post_slug', 'columns': ['slug'], 'unique': False},
#  {'name': 'idx_title_unique', 'columns': ['title'], 'unique': True}]
```

#### `table.fts_indexes`

List of FTS (full-text search) indexes on this table.

**Returns:** `list[dict]` - List of FTS index definitions: `[{'name': str, 'columns': [str], 'language': str}, ...]`

**Example:**
```python
print(articles.fts_indexes)
# [{'name': 'article_fts', 'columns': ['title', 'content'], 'language': 'english'}]
```

### Methods

#### `table.dataclass() -> type`

Generate or return a dataclass for this table.

After calling, all operations return dataclass instances instead of dicts.

**When to use:**
- Production applications where type safety matters
- When you want IDE autocomplete on database records
- Large codebases with multiple developers
- When working with typed frameworks (FastAPI, etc.)
- To catch field name typos at development time

**When NOT to use:**
- Quick scripts and prototypes
- Jupyter notebooks and interactive exploration
- When working with dynamic/varying data structures

**Important:** Call `.dataclass()` **immediately** after creating/reflecting a table to maintain consistency. Once called, ALL operations return dataclass instances. See [best-practices.md](best-practices.md#maintaining-consistency) for details.

**Returns:** `type` - Dataclass type

**Example:**
```python
UserDC = users.dataclass()

# Now returns dataclass instances
user = await users[1]  # Returns UserDC instance
print(user.name)  # Field access
```

#### `table.xtra(**kwargs) -> Table`

Return a new Table with additional filters applied to all operations.

**When to use:**
- Multi-tenant applications (filter by tenant_id)
- Row-level security and access control
- Scoped operations (only active records, only user's own data)
- Reducing repetitive WHERE clauses
- Enforcing business rules at the data layer

**When NOT to use:**
- One-time filtering (use `table.lookup()` with kwargs instead)
- Complex conditions (use raw SQL with `db.q()`)
- When filters need to change frequently

**Parameters:**
- `**kwargs`: Column=value filters

**Returns:** `Table` - New filtered table instance

**Example:**
```python
admin_users = users.xtra(role="admin")
admins = await admin_users()  # Only role='admin' users
```

#### `async table.insert(record: dict | Any) -> dict | Any`

Insert a record into the table.

**When to use:**
- Creating new records
- When you want the auto-generated primary key returned
- Single record insertion with type safety

**When NOT to use:**
- Bulk inserts (use raw SQL for better performance)
- Insert or update logic (use `upsert()` instead)

**Parameters:**
- `record` (dict | dataclass | object): Record to insert

**Returns:** Inserted record (dict or dataclass based on configuration)

**Raises:**
- `ValidationError`: xtra filter violation
- `IntegrityError`: Constraint violation (unique, foreign key, etc.)
- `RuntimeError`: Unexpected error

**Example:**
```python
user = await users.insert({
    "name": "Alice",
    "email": "alice@example.com"
})
# Returns: {'id': 1, 'name': 'Alice', 'email': 'alice@example.com'}
```

#### `async table.update(record: dict | Any) -> dict | Any`

Update a record by primary key.

**When to use:**
- Modifying existing records
- When you have the full record with PK
- Partial updates to specific fields

**When NOT to use:**
- Record might not exist (use `upsert()` instead)
- Bulk updates (use raw SQL)
- When you don't have the primary key

**Parameters:**
- `record` (dict | dataclass | object): Record with PK to update

**Returns:** Updated record

**Raises:**
- `ValidationError`: Missing PK or xtra filter violation
- `NotFoundError`: Record not found
- `IntegrityError`: Constraint violation
- `RuntimeError`: Unexpected error

**Example:**
```python
user['name'] = "Alice Smith"
updated = await users.update(user)
```

#### `async table.upsert(record: dict | Any) -> dict | Any`

Insert or update based on primary key existence.

**When to use:**
- Synchronizing data from external sources
- When you don't know if record exists
- Idempotent operations
- APIs that support both create and update

**When NOT to use:**
- When you know the operation (use `insert()` or `update()` for clarity)
- Complex business logic around creation vs updates

**Parameters:**
- `record` (dict | dataclass | object): Record to upsert

**Returns:** Upserted record

**Example:**
```python
user = await users.upsert({
    "id": 1,
    "name": "Alice Updated",
    "email": "alice@new.com"
})
```

#### `async table.delete(pk_value: Any) -> None`

Delete a record by primary key.

**When to use:**
- Removing records by known primary key
- Single record deletion
- Hard deletes (permanent removal)

**When NOT to use:**
- Bulk deletes (use raw SQL)
- Soft deletes (use `update()` to set deleted flag)
- Conditional deletes (use raw SQL with WHERE)

**Parameters:**
- `pk_value`: Primary key value (or tuple for composite keys)

**Raises:**
- `ValidationError`: Invalid PK format
- `NotFoundError`: Record not found

**Example:**
```python
await users.delete(1)

# Composite key
await order_items.delete((101, 5))  # (order_id, product_id)
```

#### `async table(limit: int = None, with_pk: bool = False) -> list`

Select records from the table.

**When to use:**
- Fetching all records (or limited subset)
- Simple SELECT * queries
- When you don't have filtering criteria
- Paginated results with `limit`

**When NOT to use:**
- Complex queries with JOINs (use `db.q()`)
- Filtered queries (use `lookup()` or `xtra()`)
- When you know the primary key (use `table[pk]` instead)

**Parameters:**
- `limit` (int, optional): Limit number of results
- `with_pk` (bool, optional): Return (pk_value, record) tuples. Defaults to False.

**Returns:** List of records (or tuples if `with_pk=True`)

**Example:**
```python
# All records
all_users = await users()

# Limited
recent = await users(limit=10)

# With primary keys
records = await users(with_pk=True)
for pk, user in records:
    print(f"PK: {pk}, Name: {user['name']}")
```

#### `async table[pk_value]`

Get a record by primary key.

**When to use:**
- Fetching a single record by known primary key
- Fast lookups by ID
- When the record must exist (raises NotFoundError if missing)

**When NOT to use:**
- When record might not exist (catch NotFoundError or use try/except)
- Filtering by non-PK columns (use `lookup()`)
- Fetching multiple records (use `table()` or `lookup()`)

**Parameters:**
- `pk_value`: Primary key value (or tuple for composite keys)

**Returns:** Record (dict or dataclass)

**Raises:**
- `ValidationError`: Invalid PK format
- `NotFoundError`: Record not found

**Example:**
```python
user = await users[1]

# Composite key
item = await order_items[(101, 5)]
```

#### `async table.lookup(**kwargs) -> dict | Any`

Find a single record matching the given criteria.

**When to use:**
- Finding a record by unique column (email, username, etc.)
- When you expect exactly one result
- Simple equality-based queries
- One-time filters

**When NOT to use:**
- Multiple matching records expected (returns first one only)
- Complex conditions (use `db.q()`)
- Repeated filters (use `xtra()` instead)
- When you have the primary key (use `table[pk]` instead)

**Parameters:**
- `**kwargs`: Column=value filters

**Returns:** Single matching record

**Raises:**
- `ValidationError`: No filter arguments provided
- `SchemaError`: Column not found
- `NotFoundError`: No matching record

**Example:**
```python
user = await users.lookup(email="alice@example.com")
```

#### `async table.drop() -> None`

Drop the table from the database.

**Example:**
```python
await users.drop()
```

#### `async table.create_index(columns: str | list[str], name: str = None, unique: bool = False) -> None`

Create an index on the table.

**When to use:**
- Adding indexes after table creation
- Performance optimization on existing tables
- Creating unique constraints on existing tables

**When NOT to use:**
- When creating a new table (use `indexes` parameter in `db.create()` instead)
- Complex index types (partial indexes, expression indexes - use raw SQL)

**Parameters:**
- `columns` (str | list[str]): Column name or list of column names for composite index
- `name` (str, optional): Index name. Auto-generated as `ix_{tablename}_{columns}` if not provided.
- `unique` (bool, optional): Create unique index. Defaults to `False`.

**Raises:**
- `ValidationError`: Column not found in table

**Example:**
```python
# Simple index with auto-generated name
await users.create_index("email")  # Creates ix_users_email

# Composite index with custom name
await posts.create_index(["author_id", "created_at"], name="idx_author_date")

# Unique index
await users.create_index("username", unique=True)
```

#### `async table.drop_index(name: str) -> None`

Drop an index from the table.

**Parameters:**
- `name` (str): Index name to drop

**Example:**
```python
await users.drop_index("ix_users_email")
await posts.drop_index("idx_author_date")
```

#### `async table.search(query: str, *, columns: list[str] = None, limit: int = None, score: bool = False) -> list`

Perform BM25 full-text search on the table's FTS-indexed columns.

**When to use:**
- Natural language search across text columns
- Relevance-ranked results (BM25 scoring)
- Finding records by keywords rather than exact match

**When NOT to use:**
- Exact string matching (use `lookup()` or `xtra()`)
- Pattern matching (use raw SQL with LIKE/GLOB)
- No FTS index exists on the table (create one first)

**Parameters:**
- `query` (str): Search query string
- `columns` (list[str], optional): Restrict search to specific indexed columns. Defaults to all indexed columns.
- `limit` (int, optional): Maximum number of results to return
- `score` (bool, optional): If True, return `(record, score)` tuples. Scores are negative floats where more negative = more relevant. Defaults to False.

**Returns:** `list` - List of matching records (dicts or dataclasses). With `score=True`, returns `list[tuple[record, float]]`.

**Raises:**
- `InvalidOperationError`: No FTS index exists on this table
- `ValidationError`: Specified columns are not FTS-indexed

**Example:**
```python
# Basic search
results = await articles.search("getting started", limit=10)

# Search specific columns only
results = await articles.search("python", columns=["title"])

# Get relevance scores
scored = await articles.search("async database", score=True)
for record, relevance in scored:
    print(f"{record['title']}: {relevance}")
# Output: "Async Database Guide: -2.5"

# Works with xtra() filters
user_articles = articles.xtra(author_id=1)
results = await user_articles.search("tutorial")
```

#### `async table.create_fts_index(columns: list[str], name: str = None, language: str = "english") -> None`

Create a full-text search index on the table.

**When to use:**
- Adding FTS capability to an existing table
- When FTS was not specified at table creation time

**When NOT to use:**
- When creating a new table (use `FTSIndex` in the `indexes` parameter of `db.create()`)

**Parameters:**
- `columns` (list[str]): Column names to include in the FTS index
- `name` (str, optional): FTS index name. Auto-generated if not provided.
- `language` (str, optional): Language for text processing (stemming, stop words). Defaults to `"english"`.

**Example:**
```python
await articles.create_fts_index(["title", "content"])
await articles.create_fts_index(["title"], name="title_fts", language="english")
```

#### `async table.drop_fts_index(name: str = None) -> None`

Drop a full-text search index from the table.

**Parameters:**
- `name` (str, optional): FTS index name to drop. If not provided, drops the default FTS index.

**Example:**
```python
await articles.drop_fts_index("article_fts")
```

#### `async table.get_parent(record, fk_column) -> dict | Any | None`

Navigate to a parent record via a foreign key column. This is the power user API for FK navigation.

**When to use:**
- Following foreign key relationships to fetch related records
- When you need explicit control over which FK to follow
- Building navigation chains across multiple tables

**When NOT to use:**
- Simple FK navigation (use `table.fk.column_name(record)` convenience API)
- Bulk loading related records (use raw SQL with JOINs via `db.q()`)

**Parameters:**
- `record` (dict | dataclass | object): Record containing the FK value
- `fk_column` (str): Name of the FK column in this table

**Returns:** Parent record (dict or dataclass based on target table's setting), or `None` if:
- FK value is `None` (nullable FK)
- Parent record not found (dangling FK)

**Raises:**
- `ValidationError`: Column doesn't exist or isn't an FK
- `SchemaError`: Referenced table not found in cache

**Example:**
```python
# Get post and navigate to its author
post = await posts[1]
author = await posts.get_parent(post, "author_id")

if author:
    print(f"Author: {author['name']}")
else:
    print("Author not found")

# Chain navigation: comment -> post -> author
comment = await comments[1]
post = await comments.get_parent(comment, "post_id")
author = await posts.get_parent(post, "author_id")
```

**Convenience API:**
```python
# Equivalent but more concise:
author = await posts.fk.author_id(post)
```

#### `async table.get_children(record, child_table, fk_column) -> list[dict | Any]`

Find child records that reference this record via a foreign key.

**When to use:**
- Finding all records that reference a parent (e.g., all posts by an author)
- Reverse FK navigation
- Building one-to-many relationship queries

**When NOT to use:**
- Complex queries with filtering (use raw SQL via `db.q()`)
- Bulk loading with multiple parents (use raw SQL with JOINs)

**Parameters:**
- `record` (dict | dataclass | object): Parent record
- `child_table` (str | Table): Child table name or Table object
- `fk_column` (str): Name of the FK column in the child table

**Returns:** `list` - List of child records (empty if no children). Respects child table's dataclass setting.

**Raises:**
- `SchemaError`: Child table not found in cache
- `ValidationError`: FK column not found in child table, or PK not extractable from record

**Example:**
```python
# Get all posts by an author
user = await users[1]
user_posts = await users.get_children(user, "post", "author_id")

# Get all comments on a post
post = await posts[1]
comments = await posts.get_children(post, "comment", "post_id")

# Using Table object instead of string
user_posts = await users.get_children(user, posts, "author_id")

# Check for empty result
if not user_posts:
    print("No posts found")
```

---

## View

Represents a database view (read-only). Inherits from Table but blocks write operations.

### Supported Operations

Views support all read operations from Table:
- `view()` - Select all
- `view[pk]` - Get by key
- `view.lookup(**kwargs)` - Find by criteria
- `view.dataclass()` - Generate dataclass
- `view.schema` - Get schema
- `view.drop()` - Drop view

### Blocked Operations

Write operations raise `InvalidOperationError`:
- `view.insert()` ❌
- `view.update()` ❌
- `view.upsert()` ❌
- `view.delete()` ❌

**Example:**
```python
view = await db.create_view("active_users", "SELECT * FROM users WHERE active = 1")

# Read operations work
users = await view()
user = await view[1]

# Write operations blocked
try:
    await view.insert({"name": "Alice"})
except InvalidOperationError as e:
    print(f"Cannot insert into view: {e}")
```

---

## Column & ColumnAccessor

### Column

Represents a database column.

#### Properties

- `column.sa_column`: Access underlying SQLAlchemy Column object

**Example:**
```python
col = users.c.name
print(col.sa_column.type)  # VARCHAR
```

### ColumnAccessor

Access columns with iteration support.

**Example:**
```python
# Access column
name_col = users.c.name

# Iterate columns
for col in users.c:
    print(col)

# Check available columns
print(dir(users.c))  # ['id', 'name', 'email', ...]
```

---

## Types

### Type Marker Classes

#### `Text`

Marker for unlimited text columns (TEXT vs VARCHAR).

```python
from deebase import Text

class Article:
    id: int
    title: str         # VARCHAR (limited)
    content: Text      # TEXT (unlimited)
```

#### `ForeignKey`

Generic type for foreign key columns. Defines a relationship to another table.

```python
from deebase import ForeignKey

class Post:
    id: int
    title: str
    author_id: ForeignKey[int, "users"]        # FK to users.id (default column)
    category_id: ForeignKey[int, "categories.id"]  # FK to categories.id (explicit)
```

**Syntax:**
- `ForeignKey[base_type, "table"]` - References `table.id`
- `ForeignKey[base_type, "table.column"]` - References `table.column`

#### `Index`

Named index definition for table creation. Use this for explicit control over index names and unique constraints.

```python
from deebase import Index

# Simple named index
idx = Index("idx_email", "email")

# Unique index
idx = Index("idx_email", "email", unique=True)

# Composite index
idx = Index("idx_author_date", "author_id", "created_at")
```

**Constructor:**
- `Index(name: str, *columns: str, unique: bool = False)`

**Parameters:**
- `name` (str): Index name
- `*columns` (str): One or more column names to index
- `unique` (bool, optional): Create unique index. Defaults to `False`.

**Raises:**
- `ValueError`: If no columns are provided

**Example usage in `db.create()`:**
```python
from deebase import Index

class Article:
    id: int
    title: str
    slug: str
    author_id: int

articles = await db.create(
    Article,
    pk='id',
    indexes=[
        "slug",                                    # Auto-named: ix_article_slug
        ("author_id", "created_at"),               # Auto-named: ix_article_author_id_created_at
        Index("idx_title", "title", unique=True),  # Named unique index
    ]
)
```

#### `FTSIndex`

Full-text search index definition for BM25 search. Used in the `indexes` parameter of `db.create()` or with `table.create_fts_index()`.

```python
from deebase import FTSIndex

# Multi-column FTS index
fts = FTSIndex("title", "content", language="english")

# Single column with custom name
fts = FTSIndex("title", name="title_fts")
```

**Constructor:**
- `FTSIndex(*columns: str, name: str = None, language: str = "english")`

**Parameters:**
- `*columns` (str): One or more column names to index for full-text search
- `name` (str, optional): FTS index name. Auto-generated if not provided.
- `language` (str, optional): Language for stemming and stop words. Defaults to `"english"`.

**Raises:**
- `ValueError`: If no columns are provided

**Example usage in `db.create()`:**
```python
from deebase import FTSIndex

class Article:
    id: int
    title: str
    content: Text

articles = await db.create(
    Article,
    pk='id',
    indexes=[
        FTSIndex("title", "content", language="english"),
    ]
)

# Search using BM25
results = await articles.search("getting started", limit=10)
```

**Backend details:**
- **SQLite**: Creates FTS5 virtual table with porter unicode61 tokenizer + auto-sync triggers
- **PostgreSQL**: Creates pg_textsearch BM25 index with `USING bm25()` syntax

**Example (ForeignKey):**
```python
from deebase import Database, ForeignKey

class User:
    id: int
    name: str

class Post:
    id: int
    author_id: ForeignKey[int, "user"]  # FK to user.id

db = Database("sqlite+aiosqlite:///:memory:")
users = await db.create(User, pk='id')
posts = await db.create(Post, pk='id')

# Enable FK enforcement in SQLite
await db.q("PRAGMA foreign_keys = ON")

# Insert parent record first
await users.insert({"id": 1, "name": "Alice"})

# Insert child record with valid FK
await posts.insert({"id": 1, "author_id": 1})

# Invalid FK raises IntegrityError
await posts.insert({"id": 2, "author_id": 999})  # IntegrityError!
```

### Type Mapping

Python type → SQLAlchemy type → Database column:

| Python Type | SQLAlchemy Type | Database Column |
|------------|-----------------|-----------------|
| `int` | `Integer` | INTEGER |
| `str` | `String` | VARCHAR |
| `Text` | `Text` | TEXT (unlimited) |
| `float` | `Float` | REAL/FLOAT |
| `bool` | `Boolean` | BOOLEAN (0/1 in SQLite) |
| `bytes` | `LargeBinary` | BLOB/BYTEA |
| `dict` | `JSON` | JSON (PostgreSQL), TEXT (SQLite) |
| `datetime.datetime` | `DateTime` | TIMESTAMP/DATETIME |
| `datetime.date` | `Date` | DATE |
| `datetime.time` | `Time` | TIME |
| `Optional[T]` | `nullable=True` | NULL-able column |
| `ForeignKey[T, "table"]` | `T` + FK constraint | FK to table.id |
| `Index` | `sa.Index` | Database index (not a column type) |

---

## Exceptions

All DeeBase exceptions inherit from `DeeBaseError`.

### `NotFoundError`

Raised when a record is not found.

**Attributes:**
- `message` (str): Error message
- `table_name` (str): Table name
- `filters` (dict): Applied filters

**Example:**
```python
from deebase import NotFoundError

try:
    user = await users[999]
except NotFoundError as e:
    print(f"Not found in {e.table_name}: {e.filters}")
```

### `IntegrityError`

Raised when a database constraint is violated.

**Attributes:**
- `message` (str): Error message
- `constraint` (str): Constraint type ('unique', 'primary_key', 'foreign_key')
- `table_name` (str): Table name

**Example:**
```python
from deebase import IntegrityError

try:
    await users.insert({"id": 1, "name": "Alice"})
    await users.insert({"id": 1, "name": "Bob"})  # Duplicate ID
except IntegrityError as e:
    print(f"Constraint {e.constraint} violated in {e.table_name}")
```

### `ConnectionError`

Raised when database connection fails.

**Attributes:**
- `message` (str): Error message
- `database_url` (str): Sanitized database URL

### `InvalidOperationError`

Raised when an invalid operation is attempted (e.g., writing to a view).

**Attributes:**
- `message` (str): Error message
- `operation` (str): Operation name
- `target` (str): Target object

### `ValidationError`

Raised when data validation fails.

**Attributes:**
- `message` (str): Error message
- `field` (str): Field name
- `value`: Invalid value

### `SchemaError`

Raised when there's a schema-related error.

**Attributes:**
- `message` (str): Error message
- `table_name` (str): Table name
- `column_name` (str): Column name

---

## Utilities

### `dataclass_src(cls: type) -> str`

Generate Python source code for a dataclass.

**When to use:**
- Inspecting generated dataclass code
- Debugging dataclass generation
- Understanding field types and defaults
- Documentation generation

**When NOT to use:**
- Exporting multiple dataclasses to files (use `create_mod()` instead)
- Programmatic code generation (just use the dataclass directly)

**Parameters:**
- `cls` (type): Dataclass to generate source for

**Returns:** `str` - Python source code

**Example:**
```python
from deebase import dataclass_src

UserDC = users.dataclass()
src = dataclass_src(UserDC)
print(src)
# from dataclasses import dataclass
# from typing import Optional
#
# @dataclass
# class User:
#     id: Optional[int] = None
#     name: Optional[str] = None
#     email: Optional[str] = None
```

### `create_mod(module_path: str, *dataclasses: type, overwrite: bool = False) -> None`

Export dataclass definitions to a Python module file.

**When to use:**
- Generating models.py from database schema
- Creating type-safe models for your application layer
- Bootstrapping a new project from an existing database
- Sharing schema definitions across projects
- When you already have dataclass instances (from `table.dataclass()`)

**When NOT to use:**
- When you want to export directly from tables (use `create_mod_from_tables()` instead)
- For single dataclass inspection (use `dataclass_src()` instead)

**Parameters:**
- `module_path` (str): Path to output .py file
- `*dataclasses` (type): Dataclass types to export
- `overwrite` (bool, optional): Overwrite if exists. Defaults to False.

**Raises:**
- `FileExistsError`: File exists and `overwrite=False`
- `ValueError`: Argument is not a dataclass

**Example:**
```python
from deebase import create_mod

# Generate dataclasses
UserDC = users.dataclass()
PostDC = posts.dataclass()

# Export to models.py
create_mod("models.py", UserDC, PostDC, overwrite=True)
```

### `create_mod_from_tables(module_path: str, *tables, overwrite: bool = False) -> None`

Export dataclass definitions from Table instances.

Convenience function that generates dataclasses from tables and exports them.

**When to use:**
- Quick export of reflected tables to Python models
- When you don't need the dataclass instances (just the file)
- One-step operation from tables to file
- Bootstrapping models from existing database

**When NOT to use:**
- When you need to work with the dataclass instances (use `table.dataclass()` then `create_mod()`)
- For single dataclass inspection (use `dataclass_src()`)

**Parameters:**
- `module_path` (str): Path to output .py file
- `*tables` (Table): Table instances to export
- `overwrite` (bool, optional): Overwrite if exists. Defaults to False.

**Example:**
```python
from deebase import create_mod_from_tables

await db.reflect()

# Export all tables to models.py
create_mod_from_tables(
    "models.py",
    db.t.users,
    db.t.posts,
    db.t.comments,
    overwrite=True
)
```

---

## API Module (FastAPI Integration)

The `deebase.api` module provides FastAPI integration for auto-generating REST CRUD endpoints from dataclass models.

**Installation:** Requires optional API dependencies:
```bash
pip install "deebase[api]"
# or: uv add "deebase[api]"
```

### `create_crud_router()`

Factory function to create a FastAPI router with CRUD endpoints.

```python
def create_crud_router(
    db: Database,
    model_cls: type,
    prefix: str = "",
    tags: list[str] = None,
    pk_field: str = "id",
    validate_fks: bool = False,
    validators: dict = None,
    exclude: set = None,
    overrides: dict = None,
) -> APIRouter
```

**When to use:**
- Auto-generating REST APIs from dataclass models
- Rapid API development with consistent CRUD patterns
- When you want FK validation before database inserts
- Building admin interfaces or CRUD-heavy applications

**When NOT to use:**
- Complex business logic (use custom routes instead)
- Non-standard REST patterns
- When you need fine-grained control over each endpoint

**Parameters:**
- `db` (Database): Database instance
- `model_cls` (type): Dataclass defining the model schema
- `prefix` (str, optional): URL prefix for routes (e.g., "/api/users")
- `tags` (list[str], optional): OpenAPI tags for grouping
- `pk_field` (str, optional): Primary key field name. Defaults to "id".
- `validate_fks` (bool, optional): Validate FK references exist before insert/update. Defaults to False.
- `validators` (dict, optional): Custom field validators/transformers
- `exclude` (set, optional): Route names to exclude: "list", "get", "create", "update", "delete"
- `overrides` (dict, optional): Custom route handlers to replace defaults. Keys: "list", "get", "create", "update", "delete"

**Returns:** `APIRouter` - FastAPI router with CRUD endpoints

**Route Customization (3 Methods):**

See [FastAPI Guide](fastapi_guide.md#route-customization) for complete documentation.

1. **`exclude`** - Remove routes:
```python
exclude={"delete"}  # No DELETE endpoint
```

2. **`overrides`** - Replace handlers with custom functions:
```python
from fastapi import Query

async def custom_list(limit: int | None = Query(None)):
    """Custom list that filters active users only."""
    users = await db.t.user(limit=limit)
    return [u for u in users if u.status == "active"]

create_crud_router(db, User, overrides={"list": custom_list})
```

3. **`CRUDRouter` subclass** - Full control with hooks:
```python
class AuditRouter(CRUDRouter):
    async def before_create(self, data: dict) -> dict:
        data["created_at"] = datetime.now().isoformat()
        return data
```

**Generated Endpoints:**
| Method | Path | Operation | Response |
|--------|------|-----------|----------|
| GET | `{prefix}/` | List all | `list[Response]` |
| GET | `{prefix}/{pk}` | Get by PK | `Response` |
| POST | `{prefix}/` | Create | `Response` (201) |
| PATCH | `{prefix}/{pk}` | Partial update | `Response` |
| DELETE | `{prefix}/{pk}` | Delete | 204 No Content |

**Example:**
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
db = Database("sqlite+aiosqlite:///app.db")

# Basic router
app.include_router(create_crud_router(
    db=db,
    model_cls=User,
    prefix="/api/users",
    tags=["Users"],
))

# Router with FK validation
app.include_router(create_crud_router(
    db=db,
    model_cls=Post,
    prefix="/api/posts",
    tags=["Posts"],
    validate_fks=True,  # Validates author_id exists before insert
))

# Router with validators and excluded routes
app.include_router(create_crud_router(
    db=db,
    model_cls=Post,
    prefix="/api/posts",
    validators={
        "title": lambda v: v.strip()[:200] if v else v,
    },
    exclude={"delete"},  # No DELETE endpoint
))
```

### `CRUDRouter`

Class for creating customizable CRUD routers with hook support.

```python
class CRUDRouter:
    def __init__(
        self,
        db: Database,
        model_cls: type,
        prefix: str = "",
        tags: list[str] = None,
        pk_field: str = "id",
        validate_fks: bool = False,
        validators: dict = None,
        exclude: set = None,
        overrides: dict = None,
    )
```

**When to use:**
- Custom hooks (before_create, after_create, etc.)
- Business logic in CRUD operations
- Access control and audit logging
- Custom validation beyond simple field transforms

**Hook Methods:**
```python
class CRUDRouter:
    async def before_create(self, data: dict) -> dict:
        """Called before INSERT. Transform or validate data."""
        return data

    async def after_create(self, record: dict) -> dict:
        """Called after INSERT. Transform response or trigger side effects."""
        return record

    async def before_update(self, pk, data: dict) -> dict:
        """Called before UPDATE. Transform or validate data."""
        return data

    async def after_update(self, record: dict) -> dict:
        """Called after UPDATE. Transform response or trigger side effects."""
        return record

    async def before_delete(self, pk) -> None:
        """Called before DELETE. Raise HTTPException to block."""
        pass

    async def after_delete(self, pk) -> None:
        """Called after DELETE. Trigger side effects."""
        pass
```

**Example with custom hooks:**
```python
from fastapi import HTTPException
from deebase.api import CRUDRouter

class PostRouter(CRUDRouter):
    async def before_create(self, data: dict) -> dict:
        # Auto-generate slug
        if 'title' in data and 'slug' not in data:
            data['slug'] = data['title'].lower().replace(' ', '-')
        return data

    async def before_delete(self, pk) -> None:
        # Block deleting published posts
        table = await self._get_table()
        post = await table[pk]
        if post.get('published'):
            raise HTTPException(
                status_code=400,
                detail="Cannot delete published posts"
            )

app = FastAPI()
post_router = PostRouter(
    db=db,
    model_cls=Post,
    prefix="/api/posts",
    tags=["Posts"],
)
app.include_router(post_router.router)
```

### `ForeignKeyValidationError`

Exception raised when FK validation fails before insert/update.

```python
from deebase.api import ForeignKeyValidationError

# Error structure
error = ForeignKeyValidationError([
    {
        "field": "author_id",
        "value": 999,
        "message": "Referenced user with id=999 does not exist"
    }
])

# Convert to dict for HTTP response
error.to_dict()
# {'type': 'foreign_key_validation_error', 'errors': [...]}
```

**HTTP Response (422):**
```json
{
    "detail": {
        "type": "foreign_key_validation_error",
        "errors": [
            {
                "field": "author_id",
                "value": 999,
                "message": "Referenced user with id=999 does not exist"
            }
        ]
    }
}
```

### Exception to HTTP Status Mapping

The API module automatically maps DeeBase exceptions to HTTP status codes:

| Exception | HTTP Status | Description |
|-----------|-------------|-------------|
| `NotFoundError` | 404 | Record not found |
| `IntegrityError` | 422 | Database constraint violation |
| `ValidationError` | 422 | Data validation failed |
| `ForeignKeyValidationError` | 422 | FK reference doesn't exist |
| `InvalidOperationError` | 400 | Invalid operation (e.g., write to view) |
| `ConnectionError` | 503 | Database connection failed |
| Other exceptions | 500 | Internal server error |

### Pydantic Model Generation

The router automatically generates Pydantic models from your dataclass:

- **CreateModel**: All fields except PK, required fields enforced
- **UpdateModel**: All fields optional (for partial updates)
- **ResponseModel**: All fields including PK

Field descriptions from `fastcore.docments()` style comments are included in OpenAPI docs:

```python
@dataclass
class User:
    id: int           # Auto-generated user ID
    name: str         # Display name
    email: str        # Email address (unique)
    status: str = "active"  # Account status
```

### Complete Example

```python
from dataclasses import dataclass
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from deebase import Database, ForeignKey, Text
from deebase.api import CRUDRouter, create_crud_router

@dataclass
class User:
    id: int
    name: str
    email: str
    status: str = "active"

@dataclass
class Post:
    id: int
    author_id: ForeignKey[int, "user"]
    title: str
    content: Text
    published: bool = False

class PostRouter(CRUDRouter):
    async def before_delete(self, pk) -> None:
        table = await self._get_table()
        post = await table[pk]
        if post.get('published'):
            raise HTTPException(400, "Cannot delete published posts")

db = Database("sqlite+aiosqlite:///blog.db")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.create(User, pk="id", if_not_exists=True)
    await db.create(Post, pk="id", if_not_exists=True)
    await db.enable_foreign_keys()
    yield
    await db.close()

app = FastAPI(lifespan=lifespan)

app.include_router(create_crud_router(
    db=db, model_cls=User,
    prefix="/api/users", tags=["Users"],
))

post_router = PostRouter(
    db=db, model_cls=Post,
    prefix="/api/posts", tags=["Posts"],
    validate_fks=True,
)
app.include_router(post_router.router)

# Run: uvicorn app:app --reload
# Docs: http://localhost:8000/docs
```

---

## Common Patterns

### Basic CRUD Workflow

```python
from deebase import Database

db = Database("sqlite+aiosqlite:///myapp.db")

# Create table
class User:
    id: int
    name: str
    email: str

users = await db.create(User, pk='id')

# INSERT
user = await users.insert({"name": "Alice", "email": "alice@example.com"})

# SELECT
all_users = await users()
user = await users[1]

# UPDATE
user['name'] = "Alice Smith"
await users.update(user)

# DELETE
await users.delete(1)

await db.close()
```

### Type-Safe Operations with Dataclasses

```python
# Generate dataclass
UserDC = users.dataclass()

# Now all operations return UserDC instances
user = await users.insert(UserDC(
    id=None,
    name="Bob",
    email="bob@example.com"
))

# Type-safe field access
print(user.name)  # IDE autocomplete works!
print(user.email)

# All CRUD operations return dataclass instances
all_users = await users()
for u in all_users:
    print(u.name)  # Type-safe
```

### Working with Existing Databases

```python
# Connect to existing database
db = Database("sqlite+aiosqlite:///existing.db")

# Reflect all tables
await db.reflect()

# Access tables
users = db.t.users
posts = db.t.posts
comments = db.t.comments

# CRUD operations work normally
user = await users[1]
all_posts = await posts()

await db.close()
```

### Filtering with xtra()

```python
# Create filtered view of table
admin_users = users.xtra(role="admin")
active_admins = admin_users.xtra(active=True)

# All operations respect filters
admins = await active_admins()  # Only role='admin' AND active=True

# Insert automatically sets filters
await active_admins.insert({"name": "Eve", "email": "eve@example.com"})
# Automatically sets role='admin' and active=True
```

### Database Views

```python
# Create view
popular_posts = await db.create_view(
    "popular_posts",
    "SELECT * FROM posts WHERE views > 1000 ORDER BY views DESC"
)

# Read operations
posts = await popular_posts()
post = await popular_posts[1]

# Access via db.v
popular = db.v.popular_posts

# Drop view
await popular_posts.drop()
```

### Exporting Models

```python
# Reflect database schema
await db.reflect()

# Export all table schemas as dataclasses
from deebase import create_mod_from_tables

create_mod_from_tables(
    "models.py",
    db.t.users,
    db.t.posts,
    db.t.comments,
    overwrite=True
)

# Now you can import from models.py
# from models import User, Post, Comment
```

### FK Navigation

```python
from deebase import Database, ForeignKey

class Author:
    id: int
    name: str

class Post:
    id: int
    author_id: ForeignKey[int, "author"]
    title: str

# Create tables
authors = await db.create(Author, pk='id')
posts = await db.create(Post, pk='id')

# Check FK metadata
print(posts.foreign_keys)
# [{'column': 'author_id', 'references': 'author.id'}]

# Forward navigation: post -> author
post = await posts[1]
author = await posts.fk.author_id(post)  # Convenience API
# or: author = await posts.get_parent(post, "author_id")  # Power user API

# Reverse navigation: author -> posts
author = await authors[1]
author_posts = await authors.get_children(author, "post", "author_id")
for p in author_posts:
    print(p['title'])
```

### Indexes

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
        "slug",                                    # Simple index
        ("author_id", "created_at"),               # Composite index
        Index("idx_title", "title", unique=True),  # Named unique index
    ]
)

# List indexes
for idx in articles.indexes:
    print(f"{idx['name']}: {idx['columns']} (unique={idx['unique']})")

# Add index after table creation
await articles.create_index("created_at")

# Drop index
await articles.drop_index("ix_article_created_at")
```

---

## Validation Module

The validation module (`deebase.validation`) provides shared validation utilities used by CLI data commands, the admin interface, and the API module. These are opt-in utilities - the core Table class does NOT use them automatically.

### apply_validators()

```python
def apply_validators(
    data: dict[str, Any],
    validators: dict[str, Callable[[Any], Any]] | None
) -> dict[str, Any]
```

Apply field validators/transformers to data.

**When to use:**
- Normalizing user input (trim whitespace, lowercase emails)
- Validating field values before database operations
- Transforming data in CLI commands or API endpoints

**Parameters:**
- `data` (dict): Record data to validate
- `validators` (dict): Mapping of field name → validator function

**Returns:** Validated (possibly transformed) data dict

**Raises:** `ValidationError` if any validator fails

**Example:**
```python
from deebase import apply_validators, ValidationError

validators = {
    "email": lambda v: v.lower().strip() if v else v,
    "name": lambda v: v.strip() if v else v,
}

# Transform data
data = {"email": "ALICE@EXAMPLE.COM", "name": "  Alice  "}
result = apply_validators(data, validators)
# result = {"email": "alice@example.com", "name": "Alice"}

# Validation error
def validate_email(v):
    if "@" not in v:
        raise ValueError("Invalid email format")
    return v.lower()

try:
    apply_validators({"email": "invalid"}, {"email": validate_email})
except ValidationError as e:
    print(e.errors)  # [{"field": "email", "message": "Invalid email format"}]
```

### apply_validators_async()

```python
async def apply_validators_async(
    data: dict[str, Any],
    validators: dict[str, Callable[[Any], Any]] | None
) -> dict[str, Any]
```

Like `apply_validators()` but supports async validator functions.

**When to use:**
- Validators that need database lookups
- Validators that call external APIs
- Any validator that needs to be async

**Example:**
```python
from deebase import apply_validators_async

async def validate_unique_email(email: str) -> str:
    existing = await users.lookup(email=email)
    if existing:
        raise ValueError("Email already exists")
    return email.lower()

validators = {"email": validate_unique_email}
result = await apply_validators_async(data, validators)
```

### validate_foreign_keys()

```python
async def validate_foreign_keys(
    db: Database,
    table: Table,
    data: dict[str, Any]
) -> None
```

Validate that FK references exist before insert/update.

**When to use:**
- Before inserting records with foreign keys
- Provides clearer error messages than database constraint failures
- Used automatically by `ValidatedTable` and API routers

**Parameters:**
- `db`: Database instance for looking up referenced tables
- `table`: Table being inserted/updated
- `data`: Record data to validate

**Raises:** `ForeignKeyValidationError` if any FK reference doesn't exist

**Example:**
```python
from deebase import validate_foreign_keys, ForeignKeyValidationError

try:
    await validate_foreign_keys(db, posts, {"author_id": 999, "title": "Test"})
except ForeignKeyValidationError as e:
    print(e.errors)
    # [{"field": "author_id", "value": 999, "message": "Referenced user with id=999 does not exist"}]
```

### ValidatedTable

```python
class ValidatedTable:
    def __init__(
        self,
        table: Table,
        validators: dict[str, Callable[[Any], Any]] | None = None,
        validate_fks: bool = True
    )
```

A wrapper that adds automatic validation to Table write operations. All read operations pass through unchanged.

**When to use:**
- Adding validation to existing tables without modifying Table class
- Enforcing business rules on writes
- Combining field validators with FK validation

**Parameters:**
- `table`: Table instance to wrap
- `validators`: Dict of field name → validator function
- `validate_fks`: Whether to validate FK references exist (default: True)

**Write Operations (with validation):**
- `insert(data)` - Validates, then inserts
- `update(data)` - Validates, then updates
- `upsert(data)` - Validates, then upserts
- `delete(pk)` - Passes through (no validation needed)

**Read Operations (passthrough):**
- `__call__(limit, with_pk)` - Select records
- `__getitem__(pk)` - Get by primary key
- `lookup(**kwargs)` - Look up by column values

**Properties (passthrough):**
- `schema`, `foreign_keys`, `indexes`, `fk`, `name`, `sa_table`

**Methods:**
- `xtra(**kwargs)` - Returns new ValidatedTable with same validators
- `dataclass()` - Get or generate dataclass
- `get_parent()`, `get_children()` - FK navigation
- `create_index()`, `drop_index()` - Index management

**Example:**
```python
from deebase import ValidatedTable

# Define validators
validators = {
    "email": lambda v: v.lower().strip() if v else v,
    "name": lambda v: v.strip() if v else v,
}

# Wrap table with validation
vusers = ValidatedTable(users, validators=validators, validate_fks=True)

# Insert through ValidatedTable - validation happens automatically
user = await vusers.insert({
    "name": "  Alice  ",  # Will be trimmed
    "email": "ALICE@EXAMPLE.COM",  # Will be lowercased
})
# user = {"id": 1, "name": "Alice", "email": "alice@example.com"}

# Read operations work unchanged
all_users = await vusers()
user = await vusers[1]

# xtra() returns ValidatedTable with same validators
active_vusers = vusers.xtra(status="active")
# active_vusers is still a ValidatedTable
```

### ForeignKeyValidationError

```python
class ForeignKeyValidationError(DeeBaseError):
    def __init__(self, errors: list[dict[str, Any]])
```

Exception raised when FK validation fails.

**Attributes:**
- `errors` (list): List of error dicts with `field`, `value`, `message` keys

**Example:**
```python
from deebase import ForeignKeyValidationError

try:
    await validate_foreign_keys(db, posts, {"author_id": 999})
except ForeignKeyValidationError as e:
    for error in e.errors:
        print(f"Field {error['field']}: {error['message']}")
```

---

## Best Practices

### Error Handling

Always catch specific exceptions:

```python
from deebase import NotFoundError, IntegrityError, ValidationError

try:
    user = await users.lookup(email=email)
except NotFoundError:
    # Handle not found
    user = await users.insert({"email": email, "name": name})
except IntegrityError as e:
    # Handle constraint violation
    print(f"Duplicate email: {e.message}")
except ValidationError as e:
    # Handle validation error
    print(f"Invalid {e.field}: {e.value}")
```

### Connection Management

Use context manager for automatic cleanup:

```python
async with Database(url) as db:
    users = await db.create(User, pk='id')
    await users.insert({"name": "Alice"})
# Automatically closed
```

### Type Safety

Use dataclasses for type safety:

```python
# Define schema class
class User:
    id: int
    name: str
    email: str

# Create table
users = await db.create(User, pk='id')

# Enable type safety
UserDC = users.dataclass()

# Now all operations are type-safe
user = await users[1]  # Type: UserDC
print(user.name)  # IDE knows this field exists
```

### Schema Evolution

For schema changes, use raw SQL:

```python
# Add column
await db.q("ALTER TABLE users ADD COLUMN age INTEGER")

# Reflect to update cache
await db.reflect_table('users')

# Now use with new schema
users = db.t.users
```
