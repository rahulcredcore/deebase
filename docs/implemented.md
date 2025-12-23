# DeeBase - Implemented Features

This document provides a detailed guide to what's currently working in DeeBase at each phase of development.

## Phase 1: Core Infrastructure ✅ COMPLETE

### Database Connection

```python
from deebase import Database

# Create database connection
db = Database("sqlite+aiosqlite:///myapp.db")

# Or use in-memory database
db = Database("sqlite+aiosqlite:///:memory:")

# Context manager support
async with Database("sqlite+aiosqlite:///myapp.db") as db:
    results = await db.q("SELECT 1")
```

### Raw SQL Queries

```python
# Execute any SQL query
results = await db.q("SELECT 1 as num")
# Returns: [{'num': 1}]

# Create tables with raw SQL
await db.q("""
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT
    )
""")

# Insert data
await db.q("INSERT INTO users (name, email) VALUES ('Alice', 'alice@example.com')")

# Query data
results = await db.q("SELECT * FROM users")
# Returns: [{'id': 1, 'name': 'Alice', 'email': 'alice@example.com'}]

# DDL/DML statements return empty list
result = await db.q("CREATE TABLE test (id INT)")
# Returns: []
```

### Type System

DeeBase includes a rich type system that maps Python types to database columns:

```python
from deebase import Text
from typing import Optional
from datetime import datetime

class Article:
    # Basic types
    id: int                    # INTEGER
    count: int                 # INTEGER
    price: float              # REAL/FLOAT
    active: bool              # BOOLEAN
    data: bytes               # BLOB/BYTEA

    # String types
    title: str                # VARCHAR (limited string)
    author: str               # VARCHAR

    # Unlimited text
    content: Text             # TEXT (unlimited)
    summary: Text             # TEXT (unlimited)

    # Structured data
    metadata: dict            # JSON (PostgreSQL) / TEXT with serialization (SQLite)
    settings: dict            # JSON

    # Temporal types
    created_at: datetime      # TIMESTAMP/DATETIME
    updated_at: datetime      # TIMESTAMP/DATETIME

    # Nullable fields
    email: Optional[str]      # VARCHAR NULL
    bio: Optional[Text]       # TEXT NULL
    tags: Optional[dict]      # JSON NULL
```

**Type Mappings:**
- `int` → INTEGER
- `str` → VARCHAR (SQLite: TEXT, PostgreSQL: VARCHAR)
- `Text` → TEXT (unlimited in both databases)
- `float` → REAL/FLOAT
- `bool` → BOOLEAN (SQLite: INTEGER 0/1)
- `bytes` → BLOB/BYTEA
- `dict` → JSON (PostgreSQL: JSON, SQLite: TEXT with auto-serialization)
- `datetime` → TIMESTAMP/DATETIME
- `date` → DATE
- `time` → TIME
- `Optional[T]` → Makes column nullable

### Access Underlying SQLAlchemy

```python
# Access the async engine
engine = db.engine

# Close database connection
await db.close()
```

### Testing

- 62 passing tests covering all Phase 1 functionality
- Async test infrastructure with pytest-asyncio
- In-memory SQLite fixtures for fast testing

---

## Phase 2: Table Creation & Schema ✅ COMPLETE

### Create Tables from Python Classes

```python
from deebase import Database, Text
from typing import Optional
from datetime import datetime

db = Database("sqlite+aiosqlite:///myapp.db")

# Simple table
class User:
    id: int
    name: str
    email: str

users = await db.create(User, pk='id')
```

### Rich Type Support

```python
# Table with Text and JSON columns
class Article:
    id: int
    title: str              # VARCHAR (short string)
    slug: str               # VARCHAR
    content: Text           # TEXT (unlimited)
    metadata: dict          # JSON column
    created_at: datetime    # TIMESTAMP

articles = await db.create(Article, pk='id')
```

### Optional/Nullable Fields

```python
class User:
    id: int                      # NOT NULL (primary key)
    name: str                    # NOT NULL (required)
    email: Optional[str]         # NULL (optional)
    bio: Optional[Text]          # NULL (optional)
    preferences: Optional[dict]  # NULL (optional)

users = await db.create(User, pk='id')

# Verify nullable properties
assert users.sa_table.c['id'].nullable is False
assert users.sa_table.c['name'].nullable is False
assert users.sa_table.c['email'].nullable is True
```

### Primary Key Configuration

```python
# Default primary key (uses 'id')
class Product:
    id: int
    name: str
    price: float

products = await db.create(Product)  # pk='id' is default

# Custom primary key
class Item:
    item_id: int
    name: str

items = await db.create(Item, pk='item_id')

# Composite primary key
class OrderItem:
    order_id: int
    product_id: int
    quantity: int

order_items = await db.create(OrderItem, pk=['order_id', 'product_id'])
```

### Table Schema

```python
class User:
    id: int
    name: str
    email: Optional[str]

users = await db.create(User, pk='id')

# Get CREATE TABLE SQL
schema = users.schema
print(schema)
# Output:
# CREATE TABLE user (
#   id INTEGER NOT NULL,
#   name VARCHAR NOT NULL,
#   email VARCHAR,
#   PRIMARY KEY (id)
# )
```

### Drop Tables

```python
# Create a table
class TempTable:
    id: int
    value: str

temp = await db.create(TempTable, pk='id')

# Drop the table
await temp.drop()

# Table is now removed from database
```

### Access SQLAlchemy Objects

```python
users = await db.create(User, pk='id')

# Access underlying SQLAlchemy Table
sa_table = users.sa_table

# Access columns
id_column = users.sa_table.c['id']
name_column = users.sa_table.c['name']

# Access primary key
pk_columns = users.sa_table.primary_key
```

### Table Caching

```python
# Tables are cached after creation
users = await db.create(User, pk='id')

# Get from cache
cached_users = db._get_table('user')
assert cached_users is users
```

### Complete Example

```python
from deebase import Database, Text
from typing import Optional
from datetime import datetime

async def main():
    # Create database
    db = Database("sqlite+aiosqlite:///blog.db")

    # Define table structure
    class Article:
        id: int
        title: str                      # VARCHAR (short string)
        slug: str                       # VARCHAR
        author: str                     # VARCHAR
        content: Text                   # TEXT (unlimited)
        excerpt: Optional[str]          # VARCHAR NULL
        metadata: dict                  # JSON
        published: bool                 # BOOLEAN
        view_count: int                 # INTEGER
        created_at: datetime            # TIMESTAMP
        updated_at: Optional[datetime]  # TIMESTAMP NULL

    # Create table
    articles = await db.create(Article, pk='id')

    # View schema
    print(articles.schema)

    # Access SQLAlchemy objects
    print(f"Table name: {articles.sa_table.name}")
    print(f"Columns: {list(articles.sa_table.columns.keys())}")
    print(f"Primary key: {[c.name for c in articles.sa_table.primary_key]}")

    # Clean up
    await articles.drop()
    await db.close()

# Run
import asyncio
asyncio.run(main())
```

### Testing

- 78 total passing tests (62 from Phase 1 + 16 new)
- Complete test coverage for:
  - Table creation with all type combinations
  - Text and JSON column types
  - Optional/nullable fields
  - Primary key configurations (default, custom, composite)
  - Schema generation
  - Table dropping
  - Error handling

---

## What's Next: Phase 3 - CRUD Operations

Coming soon:
- `table.insert()` - Insert records
- `table.update()` - Update records
- `table.upsert()` - Insert or update
- `table.delete()` - Delete records
- `table()` - Select all/limited records
- `table[pk]` - Get by primary key
- `table.lookup()` - Query with WHERE conditions

All operations will support both dict and dataclass modes.

---

## Error Handling

```python
# No type annotations
class Empty:
    pass

await db.create(Empty)
# Raises: ValueError: Class Empty has no type annotations

# Invalid primary key
class User:
    id: int
    name: str

await db.create(User, pk='user_id')
# Raises: ValueError: Primary key column 'user_id' not found in class annotations

# Drop non-existent table twice
temp = await db.create(TempTable, pk='id')
await temp.drop()
await temp.drop()
# Raises: SQLAlchemy exception (table doesn't exist)
```

---

## Phase 3: CRUD Operations ✅ COMPLETE

Phase 3 implements all CRUD (Create, Read, Update, Delete) operations with full support for:
- ✨ Insert records with auto-generated PKs
- ✨ Select all/limited records
- ✨ Get records by primary key
- ✨ Lookup records by WHERE conditions
- ✨ Update existing records
- ✨ Delete records
- ✨ Upsert (insert or update)
- ✨ Composite primary keys
- ✨ Rich types (Text, JSON, datetime)
- ✨ xtra() filtering
- ✨ Error handling with NotFoundError

### Insert Records

```python
from deebase import Database

db = Database("sqlite+aiosqlite:///myapp.db")

class User:
    id: int
    name: str
    email: str
    age: int

users = await db.create(User, pk='id')

# Insert a record (returns inserted record with auto-generated ID)
user = await users.insert({
    "name": "Alice",
    "email": "alice@example.com",
    "age": 30
})
print(user)
# {'id': 1, 'name': 'Alice', 'email': 'alice@example.com', 'age': 30}

# Insert multiple records
user2 = await users.insert({"name": "Bob", "email": "bob@example.com", "age": 25})
user3 = await users.insert({"name": "Charlie", "email": "charlie@example.com", "age": 35})
```

### Select Records

```python
# Select all records
all_users = await users()
# Returns: [{'id': 1, ...}, {'id': 2, ...}, {'id': 3, ...}]

# Select with limit
recent_users = await users(limit=2)
# Returns: [{'id': 1, ...}, {'id': 2, ...}]

# Select with primary key values (with_pk=True)
results = await users(with_pk=True)
# Returns: [(1, {'id': 1, ...}), (2, {'id': 2, ...}), ...]
for pk, record in results:
    print(f"PK={pk}: {record['name']}")
```

### Get by Primary Key

```python
# Get single record by PK
user = await users[1]
print(user)
# {'id': 1, 'name': 'Alice', 'email': 'alice@example.com', 'age': 30}

# NotFoundError if not found
from deebase import NotFoundError

try:
    missing = await users[999]
except NotFoundError:
    print("User not found")
```

### Lookup by Conditions

```python
# Find single record by column value(s)
user = await users.lookup(email="alice@example.com")
print(user['name'])  # 'Alice'

# Multiple conditions
user = await users.lookup(name="Bob", age=25)

# NotFoundError if not found
try:
    user = await users.lookup(email="nonexistent@example.com")
except NotFoundError:
    print("No matching user")
```

### Update Records

```python
# Update a record (must include PK)
updated = await users.update({
    "id": 1,
    "name": "Alice Smith",
    "email": "alice.smith@example.com",
    "age": 31
})
print(updated)
# {'id': 1, 'name': 'Alice Smith', 'email': 'alice.smith@example.com', 'age': 31}

# Can also fetch, modify, and update
user = await users[1]
user['age'] += 1
updated = await users.update(user)

# NotFoundError if PK doesn't exist
try:
    await users.update({"id": 999, "name": "Ghost", "email": "ghost@example.com", "age": 0})
except NotFoundError:
    print("User not found")
```

### Delete Records

```python
# Delete by primary key
await users.delete(1)

# Record is now gone
try:
    await users[1]
except NotFoundError:
    print("User was deleted")

# NotFoundError if already deleted
try:
    await users.delete(1)
except NotFoundError:
    print("User already deleted")
```

### Upsert (Insert or Update)

```python
class Product:
    id: int
    name: str
    price: float
    stock: int

products = await db.create(Product, pk='id')

# Upsert without ID → inserts new record
product = await products.upsert({
    "name": "Widget",
    "price": 9.99,
    "stock": 100
})
print(product['id'])  # 1 (auto-generated)

# Upsert with existing ID → updates record
updated = await products.upsert({
    "id": 1,
    "name": "Super Widget",
    "price": 14.99,
    "stock": 150
})
print(updated)
# {'id': 1, 'name': 'Super Widget', 'price': 14.99, 'stock': 150}

# Only one record exists
all_products = await products()
print(len(all_products))  # 1
```

### Composite Primary Keys

```python
class OrderItem:
    order_id: int
    item_id: int
    quantity: int
    price: float

order_items = await db.create(OrderItem, pk=['order_id', 'item_id'])

# Insert with composite PK
item = await order_items.insert({
    "order_id": 1,
    "item_id": 101,
    "quantity": 5,
    "price": 9.99
})

# Get by composite PK (use tuple)
item = await order_items[(1, 101)]
print(item)
# {'order_id': 1, 'item_id': 101, 'quantity': 5, 'price': 9.99}

# Update with composite PK
updated = await order_items.update({
    "order_id": 1,
    "item_id": 101,
    "quantity": 10,
    "price": 9.99
})

# Delete by composite PK (use tuple)
await order_items.delete((1, 101))

# with_pk returns tuple for composite PKs
results = await order_items(with_pk=True)
for pk, record in results:
    print(f"PK={pk}")  # PK=(1, 101)
```

### Rich Types (Text, JSON, datetime)

```python
from deebase import Text
from datetime import datetime

class BlogPost:
    id: int
    title: str              # VARCHAR
    slug: str               # VARCHAR
    content: Text           # TEXT (unlimited)
    metadata: dict          # JSON
    created_at: datetime    # TIMESTAMP

posts = await db.create(BlogPost, pk='id')

# Insert with rich types
post = await posts.insert({
    "title": "Getting Started",
    "slug": "getting-started",
    "content": "A" * 10000,  # Very long text
    "metadata": {
        "author": "Alice",
        "tags": ["python", "tutorial"],
        "views": 0
    },
    "created_at": datetime.now()
})

print(len(post['content']))  # 10000
print(post['metadata']['author'])  # 'Alice'
print(type(post['created_at']))  # datetime

# Update JSON field
post['metadata']['views'] = 100
post['metadata']['tags'].append("database")
updated = await posts.update(post)
print(updated['metadata'])
# {'author': 'Alice', 'tags': ['python', 'tutorial', 'database'], 'views': 100}
```

### xtra() Filtering

The `xtra()` method creates a filtered view of a table that applies to all CRUD operations:

```python
class Post:
    id: int
    title: str
    user_id: int

posts = await db.create(Post, pk='id')

# Insert some posts
await posts.insert({"title": "Post 1", "user_id": 1})
await posts.insert({"title": "Post 2", "user_id": 1})
await posts.insert({"title": "Post 3", "user_id": 2})

# Create filtered view for user 1
user1_posts = posts.xtra(user_id=1)

# SELECT respects filter
my_posts = await user1_posts()
print(len(my_posts))  # 2 (only user_id=1)

# INSERT auto-sets filter value
new_post = await user1_posts.insert({"title": "Post 4"})
print(new_post['user_id'])  # 1 (automatically set)

# LOOKUP respects filter
found = await user1_posts.lookup(title="Post 1")  # Works
try:
    found = await user1_posts.lookup(title="Post 3")  # Fails (user_id=2)
except NotFoundError:
    print("Post not accessible through this filter")

# DELETE respects filter
await user1_posts.delete(1)  # Works if post 1 is user_id=1
try:
    await user1_posts.delete(3)  # Fails (post 3 is user_id=2)
except NotFoundError:
    print("Cannot delete post from other user")

# Original table is unchanged
all_posts = await posts()
print(len(all_posts))  # Still shows all posts
```

### Full CRUD Cycle Example

```python
from deebase import Database, NotFoundError

db = Database("sqlite+aiosqlite:///myapp.db")

class Task:
    id: int
    title: str
    completed: bool

tasks = await db.create(Task, pk='id')

# CREATE
task = await tasks.insert({"title": "Learn DeeBase", "completed": False})
task_id = task['id']
print(f"Created task {task_id}")

# READ
fetched = await tasks[task_id]
print(f"Task: {fetched['title']}, completed: {fetched['completed']}")

# READ ALL
all_tasks = await tasks()
print(f"Total tasks: {len(all_tasks)}")

# UPDATE
fetched['completed'] = True
updated = await tasks.update(fetched)
print(f"Updated task: {updated['completed']}")  # True

# DELETE
await tasks.delete(task_id)
print(f"Deleted task {task_id}")

# Verify deletion
try:
    await tasks[task_id]
except NotFoundError:
    print("Task successfully deleted")
```

### Error Handling

```python
from deebase import NotFoundError

users = await db.create(User, pk='id')

# Get non-existent record
try:
    user = await users[999]
except NotFoundError as e:
    print(f"Error: {e}")  # "Record with PK 999 not found"

# Lookup non-existent record
try:
    user = await users.lookup(email="missing@example.com")
except NotFoundError as e:
    print(f"Error: {e}")  # "No record found matching {'email': '...'}"

# Update non-existent record
try:
    await users.update({"id": 999, "name": "Ghost", "email": "ghost@example.com"})
except NotFoundError as e:
    print(f"Error: {e}")  # "Record with PK {'id': 999} not found..."

# Delete non-existent record
try:
    await users.delete(999)
except NotFoundError as e:
    print(f"Error: {e}")  # "Record with PK 999 not found..."
```

### Testing

- **27 new Phase 3 tests** - All passing ✅
- **105 total tests** (Phase 1 + 2 + 3) - All passing ✅
- Comprehensive coverage:
  - Basic CRUD with dicts
  - Composite primary keys
  - Rich types (Text, JSON, datetime, Optional)
  - xtra() filtering on all operations
  - Error handling and edge cases
  - with_pk parameter

---

## Phase 4: Dataclass Support ✅ COMPLETE

Phase 4 adds full dataclass support for type-safe database operations:
- ✨ Generate dataclasses from table metadata with `.dataclass()`
- ✨ CRUD operations with dataclass instances
- ✨ Support for actual `@dataclass` decorated classes
- ✨ Mix dict and dataclass inputs seamlessly
- ✨ IDE autocomplete and type checking
- ✨ Optional field generation for auto-increment PKs

### Generate Dataclass from Table

```python
from deebase import Database

db = Database("sqlite+aiosqlite:///myapp.db")

# Create table with plain class (not @dataclass)
class User:
    id: int
    name: str
    email: str
    age: int

users = await db.create(User, pk='id')

# Before calling .dataclass() - operations return dicts
user_dict = await users.insert({"name": "Alice", "email": "alice@example.com", "age": 30})
print(type(user_dict))  # <class 'dict'>

# Generate dataclass from table metadata
UserDC = users.dataclass()
print(UserDC)  # <class 'deebase.dataclass_utils.User'>

# After calling .dataclass() - operations return dataclass instances
user_dc = await users.insert({"name": "Bob", "email": "bob@example.com", "age": 25})
print(type(user_dc))  # <class 'deebase.dataclass_utils.User'>
print(user_dc.name)   # 'Bob' - field access works!
```

### CRUD with Dataclass Instances

```python
# Enable dataclass mode
UserDC = users.dataclass()

# INSERT with dataclass instance
alice = await users.insert(UserDC(id=None, name="Alice", email="alice@example.com", age=30))
print(alice)  # User(id=1, name='Alice', email='alice@example.com', age=30)

# INSERT with dict still works
bob = await users.insert({"name": "Bob", "email": "bob@example.com", "age": 25})
print(bob)  # User(id=2, name='Bob', email='bob@example.com', age=25)

# SELECT returns dataclass instances
all_users = await users()
for user in all_users:
    print(f"{user.name}: {user.age} years old")  # Field access!

# GET by PK returns dataclass
user = await users[1]
print(user.name)  # 'Alice'

# LOOKUP returns dataclass
found = await users.lookup(email="bob@example.com")
print(found.name)  # 'Bob'

# UPDATE with dataclass instance
alice.age = 31
updated = await users.update(alice)
print(updated.age)  # 31

# UPDATE with dict still works
await users.update({"id": 2, "name": "Bob", "email": "bob@example.com", "age": 26})
```

### Using Actual @dataclass

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class Product:
    id: Optional[int] = None
    name: str = ""
    price: float = 0.0
    stock: int = 0

# Create table from @dataclass
products = await db.create(Product, pk='id')

# Insert with @dataclass instance
widget = await products.insert(Product(name="Widget", price=9.99, stock=100))
print(widget)  # Product(id=1, name='Widget', price=9.99, stock=100)
print(isinstance(widget, Product))  # True

# All operations automatically use the @dataclass
gadget = await products.insert(Product(name="Gadget", price=14.99, stock=50))

# Select returns @dataclass instances
all_products = await products()
for product in all_products:
    print(f"{product.name}: ${product.price}")
```

### Dataclass with Rich Types

```python
from deebase import Text
from datetime import datetime

class Article:
    id: int
    title: str
    content: Text           # TEXT (unlimited)
    metadata: dict          # JSON
    published: datetime     # TIMESTAMP

articles = await db.create(Article, pk='id')
ArticleDC = articles.dataclass()

# Insert with rich types
article = await articles.insert(ArticleDC(
    id=None,
    title="Getting Started",
    content="A" * 10000,  # Very long text
    metadata={"author": "Alice", "tags": ["tutorial"]},
    published=datetime.now()
))

print(article.title)                 # 'Getting Started'
print(len(article.content))          # 10000
print(article.metadata['author'])    # 'Alice'
print(type(article.published))       # <class 'datetime.datetime'>
```

### Type Safety Benefits

```python
# Enable dataclass mode
UserDC = users.dataclass()

# IDE autocomplete works!
all_users = await users()
for user in all_users:
    # Your IDE knows about .name, .email, .age
    print(user.name.upper())
    print(user.age + 1)

# Type checking with mypy/pyright
def process_user(user: UserDC):
    """Type hints work with generated dataclasses."""
    return user.name.upper()

# Field access catches typos at development time
user = await users[1]
print(user.name)   # ✓ Works
print(user.naem)   # ✗ IDE catches typo!
```

### Mixing Dict and Dataclass Inputs

```python
class Cat:
    id: int
    name: str
    weight: float

cats = await db.create(Cat, pk='id')
CatDC = cats.dataclass()

# Insert with dict
tom = await cats.insert({"name": "Tom", "weight": 10.2})
print(type(tom))  # <class 'deebase.dataclass_utils.Cat'>

# Insert with dataclass
fluffy = await cats.insert(CatDC(id=None, name="Fluffy", weight=8.5))
print(type(fluffy))  # <class 'deebase.dataclass_utils.Cat'>

# Update with dict
await cats.update({"id": tom.id, "name": "Tom", "weight": 10.5})

# Update with dataclass
fluffy.weight = 9.0
await cats.update(fluffy)

# Both work seamlessly!
```

### Before and After .dataclass()

```python
class Book:
    id: int
    title: str
    author: str

books = await db.create(Book, pk='id')

# BEFORE: Returns dicts
book1 = await books.insert({"title": "1984", "author": "George Orwell"})
print(type(book1))  # <class 'dict'>
print(book1['title'])  # '1984'

# Enable dataclass mode
BookDC = books.dataclass()

# AFTER: Returns dataclass instances
book2 = await books.insert({"title": "Brave New World", "author": "Aldous Huxley"})
print(type(book2))  # <class 'deebase.dataclass_utils.Book'>
print(book2.title)  # 'Brave New World' - field access!

# Existing records are returned as dataclasses
all_books = await books()
print(type(all_books[0]))  # <class 'deebase.dataclass_utils.Book'>
print(all_books[0].title)  # '1984'
```

### Generated Dataclass Fields

```python
# Generated dataclasses have Optional fields for auto-increment PKs
UserDC = users.dataclass()

# Fields are Optional (default None) to handle auto-generated IDs
user = UserDC(id=None, name="Alice", email="alice@example.com", age=30)
print(user.id)  # None

# After insert, ID is populated
inserted = await users.insert(user)
print(inserted.id)  # 1 (auto-generated)
```

### Complete Example

```python
from deebase import Database, Text
from datetime import datetime

db = Database("sqlite+aiosqlite:///myapp.db")

class BlogPost:
    id: int
    title: str
    content: Text
    metadata: dict
    created_at: datetime

posts = await db.create(BlogPost, pk='id')

# Enable dataclass mode for type safety
PostDC = posts.dataclass()

# Create post with dataclass instance
post = await posts.insert(PostDC(
    id=None,
    title="My First Post",
    content="Long content here...",
    metadata={"author": "Alice", "tags": ["intro"]},
    created_at=datetime.now()
))

# Type-safe field access
print(f"Title: {post.title}")
print(f"Author: {post.metadata['author']}")
print(f"Created: {post.created_at}")

# Update with dataclass
post.metadata['views'] = 100
updated = await posts.update(post)

# Select with type safety
all_posts = await posts()
for p in all_posts:
    print(f"{p.title}: {p.metadata.get('views', 0)} views")
```

### Testing

- **20 new Phase 4 tests** - All passing ✅
- **125 total tests** (Phase 1-4) - All passing ✅
- Comprehensive coverage:
  - Dataclass generation from table metadata
  - CRUD with dataclass instances
  - Actual `@dataclass` support
  - Mixing dict and dataclass inputs
  - Rich types with dataclasses
  - Before/after `.dataclass()` behavior

---

## Dependencies

- Python 3.14+
- sqlalchemy 2.0.45+ (with async support)
- aiosqlite 0.22.0+ (async SQLite driver)
- greenlet 3.3.0+ (required for SQLAlchemy async)
- pytest + pytest-asyncio (for testing)

---

## Database Support

Currently tested with:
- ✅ SQLite (via aiosqlite)
- 🚧 PostgreSQL (via asyncpg) - infrastructure ready, not yet tested

The codebase is designed to be database-agnostic through SQLAlchemy's dialect system.
