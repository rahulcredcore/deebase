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

#### `async db.create(cls: type, pk: str | list[str] = None) -> Table`

Create a table from a Python class with type annotations.

**Parameters:**
- `cls` (type): Class with type annotations defining schema
- `pk` (str | list[str], optional): Primary key column name(s). Defaults to `'id'`.

**Returns:** `Table` - Table instance

**Raises:**
- `ValidationError`: Class has no type annotations
- `SchemaError`: Primary key column not found in annotations

**Example:**
```python
class User:
    id: int
    name: str
    email: str
    created_at: datetime

users = await db.create(User, pk='id')

# Composite primary key
class OrderItem:
    order_id: int
    product_id: int
    quantity: int

order_items = await db.create(OrderItem, pk=['order_id', 'product_id'])
```

#### `async db.reflect(schema: str = None) -> None`

Reflect all tables from the database into cache.

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

**Parameters:**
- `name` (str): View name to reflect

**Returns:** `View` - Reflected view instance

**Example:**
```python
view = await db.reflect_view('active_users')
# Also makes db.v.active_users available
```

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

### Methods

#### `table.dataclass() -> type`

Generate or return a dataclass for this table.

After calling, all operations return dataclass instances instead of dicts.

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
