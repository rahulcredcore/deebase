# Migrating from fastlite to DeeBase

This guide helps fastlite users transition to DeeBase.

## Overview

DeeBase is designed to replicate the fastlite API while adding async support and multi-database compatibility. Most concepts translate directly, with the main difference being async/await syntax.

## Key Differences

| Feature | fastlite | DeeBase |
|---------|----------|---------|
| **Async Support** | Synchronous | Async (requires `await`) |
| **Database Backend** | sqlite-utils | SQLAlchemy |
| **Supported Databases** | SQLite only | SQLite + PostgreSQL |
| **Connection** | Default file or explicit | Always explicit connection string |
| **Import** | `from fastlite import database` | `from deebase import Database` |

## Quick Migration Checklist

1. ✅ Add `async`/`await` to all database operations
2. ✅ Change `database()` → `Database(url)`
3. ✅ Update function definitions to `async def`
4. ✅ Use connection strings (no default database file)
5. ✅ Handle errors with new exception types

## Side-by-Side Comparison

### Database Creation

**fastlite:**
```python
from fastlite import database

# Uses default database.db
db = database()

# Or specify file
db = database('myapp.db')
```

**DeeBase:**
```python
from deebase import Database

# Always specify connection string
db = Database("sqlite+aiosqlite:///myapp.db")

# In-memory database
db = Database("sqlite+aiosqlite:///:memory:")

# PostgreSQL
db = Database("postgresql+asyncpg://user:pass@localhost/dbname")
```

### Table Creation

**fastlite:**
```python
class User:
    id: int
    name: str
    email: str

users = db.create(User, pk='id')
```

**DeeBase:**
```python
class User:
    id: int
    name: str
    email: str

users = await db.create(User, pk='id')  # async!
```

**Changes:**
- Add `await` before `db.create()`

### Raw SQL Queries

**fastlite:**
```python
# SELECT returns list of dicts
results = db.q("SELECT * FROM users WHERE age > 18")

# DDL/DML
db.q("CREATE TABLE products (id INT PRIMARY KEY, name TEXT)")
db.q("INSERT INTO products VALUES (1, 'Widget')")
```

**DeeBase:**
```python
# SELECT returns list of dicts
results = await db.q("SELECT * FROM users WHERE age > 18")  # async!

# DDL/DML
await db.q("CREATE TABLE products (id INT PRIMARY KEY, name TEXT)")
await db.q("INSERT INTO products VALUES (1, 'Widget')")
```

**Changes:**
- Add `await` before `db.q()`

### INSERT Operations

**fastlite:**
```python
user = users.insert({"name": "Alice", "email": "alice@example.com"})
```

**DeeBase:**
```python
user = await users.insert({"name": "Alice", "email": "alice@example.com"})
```

**Changes:**
- Add `await` before `users.insert()`

### SELECT Operations

**fastlite:**
```python
# All records
all_users = users()

# With limit
recent = users(limit=10)

# Get by primary key
user = users[1]

# Lookup by column
user = users.lookup(email="alice@example.com")
```

**DeeBase:**
```python
# All records
all_users = await users()

# With limit
recent = await users(limit=10)

# Get by primary key
user = await users[1]

# Lookup by column
user = await users.lookup(email="alice@example.com")
```

**Changes:**
- Add `await` before all select operations

### UPDATE Operations

**fastlite:**
```python
user['name'] = "Alice Smith"
updated = users.update(user)
```

**DeeBase:**
```python
user['name'] = "Alice Smith"
updated = await users.update(user)
```

**Changes:**
- Add `await` before `users.update()`

### DELETE Operations

**fastlite:**
```python
users.delete(1)
```

**DeeBase:**
```python
await users.delete(1)
```

**Changes:**
- Add `await` before `users.delete()`

### UPSERT Operations

**fastlite:**
```python
user = users.upsert({"id": 1, "name": "Alice", "email": "alice@example.com"})
```

**DeeBase:**
```python
user = await users.upsert({"id": 1, "name": "Alice", "email": "alice@example.com"})
```

**Changes:**
- Add `await` before `users.upsert()`

### Dataclass Support

**fastlite:**
```python
# Generate dataclass
UserDC = users.dataclass()

# Use in operations
user = users.insert(UserDC(id=None, name="Alice", email="alice@example.com"))
all_users = users()  # Returns list of UserDC instances
```

**DeeBase:**
```python
# Generate dataclass
UserDC = users.dataclass()  # synchronous!

# Use in operations
user = await users.insert(UserDC(id=None, name="Alice", email="alice@example.com"))
all_users = await users()  # Returns list of UserDC instances
```

**Changes:**
- `.dataclass()` is synchronous (no await)
- Add `await` to CRUD operations

### xtra() Filtering

**fastlite:**
```python
admin_users = users.xtra(role="admin")
admins = admin_users()
```

**DeeBase:**
```python
admin_users = users.xtra(role="admin")  # synchronous!
admins = await admin_users()  # async!
```

**Changes:**
- `.xtra()` is synchronous (no await)
- Add `await` when calling filtered table

### Table Reflection

**fastlite:**
```python
# Reflect all tables
db.t  # Auto-loads tables lazily

# Access any table
users = db.t.users
posts = db.t.posts
```

**DeeBase:**
```python
# Reflect all tables (explicit)
await db.reflect()

# Access cached tables (synchronous)
users = db.t.users
posts = db.t.posts
```

**Changes:**
- Call `await db.reflect()` explicitly before accessing `db.t`
- `db.t.tablename` is synchronous (cache lookup)

### Views

**fastlite:**
```python
view = db.create_view("popular_posts", "SELECT * FROM posts WHERE views > 1000")
posts = view()
```

**DeeBase:**
```python
view = await db.create_view("popular_posts", "SELECT * FROM posts WHERE views > 1000")
posts = await view()
```

**Changes:**
- Add `await` to `db.create_view()`
- Add `await` to view queries

### Error Handling

**fastlite:**
```python
from fastlite import NotFoundError

try:
    user = users[999]
except NotFoundError:
    print("User not found")
```

**DeeBase:**
```python
from deebase import NotFoundError

try:
    user = await users[999]  # async!
except NotFoundError as e:
    print(f"User not found in {e.table_name}")
    print(f"Filters: {e.filters}")
```

**Changes:**
- Add `await` to operations
- DeeBase exceptions have additional attributes (table_name, filters, etc.)
- More exception types available (IntegrityError, ValidationError, SchemaError, etc.)

## Complete Migration Example

### fastlite Code

```python
from fastlite import database

# Create/connect to database
db = database('myapp.db')

# Define schema
class User:
    id: int
    name: str
    email: str
    active: bool = True

# Create table
users = db.create(User, pk='id')

# Insert
alice = users.insert({"name": "Alice", "email": "alice@example.com"})
bob = users.insert({"name": "Bob", "email": "bob@example.com"})

# Query
all_users = users()
user = users[alice['id']]

# Update
user['active'] = False
users.update(user)

# Delete
users.delete(bob['id'])

# xtra filtering
active_users = users.xtra(active=True)
active = active_users()

# Generate dataclass
UserDC = users.dataclass()
```

### DeeBase Code

```python
from deebase import Database

async def main():
    # Create/connect to database
    db = Database("sqlite+aiosqlite:///myapp.db")

    # Define schema (same!)
    class User:
        id: int
        name: str
        email: str
        active: bool = True

    # Create table (async!)
    users = await db.create(User, pk='id')

    # Insert (async!)
    alice = await users.insert({"name": "Alice", "email": "alice@example.com"})
    bob = await users.insert({"name": "Bob", "email": "bob@example.com"})

    # Query (async!)
    all_users = await users()
    user = await users[alice['id']]

    # Update (async!)
    user['active'] = False
    await users.update(user)

    # Delete (async!)
    await users.delete(bob['id'])

    # xtra filtering (xtra is sync, queries are async)
    active_users = users.xtra(active=True)
    active = await active_users()

    # Generate dataclass (sync!)
    UserDC = users.dataclass()

    # Close connection
    await db.close()

# Run async code
import asyncio
asyncio.run(main())
```

**Key Changes:**
1. Wrap everything in `async def main()`
2. Add `await` before all database operations
3. Use explicit connection string
4. Call `asyncio.run(main())` to execute

## FastAPI Integration

DeeBase is designed for async web frameworks like FastAPI.

### Basic Integration

```python
from fastapi import FastAPI, Depends
from deebase import Database, NotFoundError

app = FastAPI()

# Database dependency
def get_db():
    db = Database("sqlite+aiosqlite:///myapp.db")
    return db

@app.on_event("startup")
async def startup():
    db = get_db()
    # Create tables on startup
    class User:
        id: int
        name: str
        email: str

    await db.create(User, pk='id')

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

@app.post("/users")
async def create_user(user_data: dict, db: Database = Depends(get_db)):
    users = db.t.users
    return await users.insert(user_data)
```

## Type Handling Differences

### Text Type

Both fastlite and DeeBase use `Text` for unlimited text:

**fastlite:**
```python
from fastlite import Text

class Article:
    title: str      # VARCHAR
    content: Text   # TEXT (unlimited)
```

**DeeBase:**
```python
from deebase import Text

class Article:
    title: str      # VARCHAR
    content: Text   # TEXT (unlimited)
```

### JSON Type

Both use `dict` for JSON columns:

```python
class Product:
    id: int
    metadata: dict  # JSON column
```

### Optional Types

Both handle Optional the same way:

```python
from typing import Optional

class User:
    id: int
    bio: Optional[str] = None  # Nullable column
```

## Advanced Features

### Composite Primary Keys

**fastlite:**
```python
order_items = db.create(OrderItem, pk=['order_id', 'product_id'])
```

**DeeBase:**
```python
order_items = await db.create(OrderItem, pk=['order_id', 'product_id'])
```

### with_pk Parameter

**fastlite:**
```python
records = users(with_pk=True)
for pk, user in records:
    print(f"PK: {pk}, Name: {user['name']}")
```

**DeeBase:**
```python
records = await users(with_pk=True)
for pk, user in records:
    print(f"PK: {pk}, Name: {user['name']}")
```

## Features Unique to DeeBase

### Multi-Database Support

```python
# SQLite
db = Database("sqlite+aiosqlite:///myapp.db")

# PostgreSQL
db = Database("postgresql+asyncpg://user:pass@localhost/dbname")
```

### Database Views

```python
view = await db.create_view(
    "active_users",
    "SELECT * FROM users WHERE active = 1"
)
users = await view()
```

### Enhanced Error Handling

```python
from deebase import (
    NotFoundError,
    IntegrityError,
    ValidationError,
    SchemaError,
    ConnectionError,
    InvalidOperationError
)

try:
    await users.insert(duplicate_user)
except IntegrityError as e:
    print(f"Constraint {e.constraint} violated")
except ValidationError as e:
    print(f"Invalid {e.field}: {e.value}")
except SchemaError as e:
    print(f"Schema error in {e.table_name}.{e.column_name}")
```

### Dataclass Export

```python
from deebase import dataclass_src, create_mod, create_mod_from_tables

# Generate source code
UserDC = users.dataclass()
print(dataclass_src(UserDC))

# Export to file
create_mod("models.py", UserDC, overwrite=True)

# Export from tables
create_mod_from_tables("models.py", db.t.users, db.t.posts, overwrite=True)
```

## Common Migration Issues

### Issue: "object is not awaitable"

**Problem:**
```python
users = db.create(User)  # Missing await
```

**Solution:**
```python
users = await db.create(User)  # Add await
```

### Issue: "AttributeError: Table 'users' not found"

**Problem:**
```python
users = db.t.users  # Table not reflected
```

**Solution:**
```python
await db.reflect()  # Reflect first
users = db.t.users  # Now works
```

Or:
```python
users = await db.reflect_table('users')  # Reflect specific table
```

### Issue: "Must specify connection string"

**Problem:**
```python
db = Database()  # No default
```

**Solution:**
```python
db = Database("sqlite+aiosqlite:///myapp.db")  # Always specify URL
```

### Issue: "Running async code outside async function"

**Problem:**
```python
# Top-level await not allowed in regular Python scripts
user = await users[1]
```

**Solution:**
```python
import asyncio

async def main():
    user = await users[1]
    print(user)

asyncio.run(main())
```

Or use IPython/Jupyter which supports top-level await:
```python
# In IPython/Jupyter
user = await users[1]  # Works!
```

## Performance Considerations

### Connection Pooling

DeeBase uses SQLAlchemy's async engine which includes connection pooling by default:

```python
db = Database("sqlite+aiosqlite:///myapp.db")
# Connection pool created automatically
```

### Concurrent Operations

DeeBase supports concurrent operations:

```python
import asyncio

# Run multiple queries concurrently
users_task = users()
posts_task = posts()

users_data, posts_data = await asyncio.gather(users_task, posts_task)
```

## Testing

### Testing with DeeBase

```python
import pytest
from deebase import Database

@pytest.fixture
async def db():
    """Fixture for in-memory test database."""
    db = Database("sqlite+aiosqlite:///:memory:")

    # Setup
    class User:
        id: int
        name: str

    await db.create(User, pk='id')

    yield db

    # Teardown
    await db.close()

@pytest.mark.asyncio
async def test_insert_user(db):
    users = db.t.user
    user = await users.insert({"name": "Alice"})
    assert user['name'] == "Alice"
    assert user['id'] == 1

@pytest.mark.asyncio
async def test_select_users(db):
    users = db.t.user
    await users.insert({"name": "Alice"})
    await users.insert({"name": "Bob"})

    all_users = await users()
    assert len(all_users) == 2
```

## Summary

The main steps to migrate from fastlite to DeeBase:

1. **Add async/await syntax** to all database operations
2. **Use explicit connection strings** instead of default database file
3. **Wrap code in async functions** and use `asyncio.run()` or async frameworks
4. **Call `await db.reflect()`** before accessing `db.t.tablename`
5. **Update imports** from `fastlite` to `deebase`
6. **Update exception handling** to use new exception types

The API is intentionally similar to make migration straightforward - most changes are adding `await` keywords and using explicit connection strings.
