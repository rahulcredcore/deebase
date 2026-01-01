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

## Phase 5: Dynamic Access & Reflection ✅ COMPLETE

Phase 5 enables dynamic table access and reflection for working with existing databases:
- ✨ Explicit table reflection with `db.reflect()`
- ✨ Single table reflection with `db.reflect_table(name)`
- ✨ Fast synchronous access via `db.t.tablename`
- ✨ Multiple table access via `db.t['table1', 'table2']`
- ✨ Full CRUD on reflected tables
- ✨ Auto-caching from `db.create()`

### Reflect All Tables

```python
from deebase import Database

# Connect to existing database
db = Database("sqlite+aiosqlite:///myapp.db")

# Reflect all existing tables (one-time async operation)
await db.reflect()

# Now access tables synchronously (fast cache lookups)
users = db.t.users
posts = db.t.posts
comments = db.t.comments

# CRUD operations work immediately
all_users = await users()
user = await users[1]
await users.insert({"name": "Alice", "email": "alice@example.com"})
```

### Reflect Single Table

```python
# Create table with raw SQL during session
await db.q("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price REAL)")

# Reflect just this table
products = await db.reflect_table('products')

# Now db.t.products works
products = db.t.products  # Cache hit

# CRUD operations work
product = await products.insert({"name": "Widget", "price": 9.99})
```

### Dynamic Table Access

```python
# After reflection, access tables by attribute
users = db.t.users        # Fast sync access
posts = db.t.posts

# Or by index
users = db.t['users']
posts = db.t['posts']

# Multiple tables at once
users, posts, comments = db.t['users', 'posts', 'comments']
```

### Tables Created with db.create() - Auto-Cached

```python
# Tables created via db.create() are automatically cached
class User:
    id: int
    name: str
    email: str

users = await db.create(User, pk='id')

# Immediately available via db.t (no reflection needed)
users = db.t.user  # ✅ Works (cache hit from create)
```

### Working with Existing Databases

```python
# Scenario: Connect to existing database with tables
db = Database("sqlite+aiosqlite:///existing_app.db")

# Reflect all tables
await db.reflect()

# Access any table
customers = db.t.customers
orders = db.t.orders
products = db.t.products

# Full CRUD operations work
customer = await customers.insert({"name": "Alice", "email": "alice@example.com"})
all_orders = await orders()
product = await products[1]
found = await customers.lookup(email="alice@example.com")
```

### Mixed Workflow: db.create() + Raw SQL + Reflection

```python
db = Database("sqlite+aiosqlite:///myapp.db")

# Create some tables via db.create() (auto-cached)
class User:
    id: int
    name: str

users_table = await db.create(User, pk='id')

# Create others with raw SQL
await db.q("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT)")
await db.q("CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER)")

# Reflect the raw SQL tables
await db.reflect()

# Now all tables accessible
users = db.t.user        # From db.create() (was already cached)
products = db.t.products  # From reflection
orders = db.t.orders      # From reflection

# All support CRUD
await users.insert({"name": "Alice"})
await products.insert({"name": "Widget"})
await orders.insert({"user_id": 1})
```

### Create Table During Session

```python
# Start with some reflected tables
await db.reflect()
users = db.t.users

# Later, create a new table with raw SQL
await db.q("CREATE TABLE temp_data (id INTEGER PRIMARY KEY, value TEXT)")

# Reflect just this new table
temp = await db.reflect_table('temp_data')

# Now available via db.t
temp = db.t.temp_data  # ✅ Works

# Or re-reflect all to pick up new tables
await db.reflect()  # Re-scans database
```

### Error Handling

```python
db = Database("sqlite+aiosqlite:///myapp.db")

# Try to access table before reflection
try:
    users = db.t.users
except AttributeError as e:
    print(e)
    # "Table 'users' not found in cache. Use 'await db.reflect()' to load all tables..."

# Reflect first
await db.reflect()

# Now works
users = db.t.users  # ✅ Cache hit
```

### Reflection Preserves Schema

```python
# Create table with specific schema
await db.q("""
    CREATE TABLE products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price REAL,
        stock INTEGER DEFAULT 0
    )
""")

# Reflect
await db.reflect()
products = db.t.products

# Verify schema
print(products.schema)
# Shows complete CREATE TABLE with all columns and constraints

# Verify columns
assert 'id' in products.sa_table.c
assert 'name' in products.sa_table.c
assert products.sa_table.c['id'].primary_key is True
```

### Complete Reflection Workflow

```python
from deebase import Database

# Step 1: Connect to existing database
db = Database("sqlite+aiosqlite:///production.db")

# Step 2: Reflect all existing tables
await db.reflect()

# Step 3: Access tables dynamically
customers = db.t.customers
orders = db.t.orders
products = db.t.products

# Step 4: Enable dataclass mode for type safety
CustomerDC = customers.dataclass()
OrderDC = orders.dataclass()

# Step 5: Use full CRUD with type safety
customer = await customers.insert(CustomerDC(
    id=None,
    name="Alice",
    email="alice@example.com"
))

# Step 6: Query and manipulate data
all_customers = await customers()
for c in all_customers:
    print(c.name)  # Type-safe field access

order = await orders.insert({
    "customer_id": customer.id,
    "total": 149.99
})
```

### Testing

- **16 new Phase 5 tests** - All passing ✅
- **142 total tests** (Phases 1-5) - All passing ✅
- Comprehensive coverage:
  - Reflecting tables from raw SQL
  - Schema preservation
  - Cache management
  - Single table reflection
  - db.t.tablename access (attribute and index)
  - Multiple table access
  - Error handling
  - Complete workflows (reflect + CRUD)

---

## Phase 7: Views Support ✅ COMPLETE

Phase 7 adds database views for read-only access to derived data:
- ✨ Create views with `db.create_view()`
- ✨ Reflect existing views with `db.reflect_view()`
- ✨ Dynamic view access via `db.v.viewname`
- ✨ Read-only operations (SELECT, GET, LOOKUP)
- ✨ Write operations blocked (INSERT, UPDATE, DELETE)
- ✨ Dataclass support for views
- ✨ Drop views with `view.drop()`

### Create Views

```python
from deebase import Database

db = Database("sqlite+aiosqlite:///myapp.db")

# Create a table first
class User:
    id: int
    name: str
    email: str
    active: bool

users = await db.create(User, pk='id')

# Insert data
await users.insert({"name": "Alice", "email": "alice@example.com", "active": True})
await users.insert({"name": "Bob", "email": "bob@example.com", "active": False})

# Create a view
active_users = await db.create_view(
    "active_users",
    "SELECT * FROM user WHERE active = 1"
)

# Query the view
results = await active_users()
print(results)  # [{'id': 1, 'name': 'Alice', 'email': 'alice@example.com', 'active': 1}]
```

### Views for JOINs (Recommended Pattern)

**Views are the recommended way to handle JOIN queries in DeeBase.** Instead of adding a join API, DeeBase uses views - which let you define the JOIN once and then use it like any table.

**Key insight:** Views don't require a Python class! The database provides column metadata during reflection, so you get full DeeBase API support (select, limit, lookup, dataclass) without defining a schema.

```python
class User:
    id: int
    name: str

class Post:
    id: int
    title: str
    user_id: int
    views: int

users = await db.create(User, pk='id')
posts = await db.create(Post, pk='id')

# Insert data
await users.insert({"name": "Alice"})
await posts.insert({"title": "My Post", "user_id": 1, "views": 100})

# Create view with JOIN
posts_with_authors = await db.create_view(
    "posts_with_authors",
    """
    SELECT p.id, p.title, p.views, u.name as author_name
    FROM post p
    JOIN user u ON p.user_id = u.id
    """
)

# Full DeeBase API works - no Python class needed!
results = await posts_with_authors()               # All rows
results = await posts_with_authors(limit=10)       # With limit
found = await posts_with_authors.lookup(author_name="Alice")  # Filter

# Generate dataclass for type-safe access
PostAuthorDC = posts_with_authors.dataclass()
for row in await posts_with_authors():
    print(f"{row.title} by {row.author_name} ({row.views} views)")
```

For one-off complex queries (CTEs, ad-hoc joins), use `db.q()`:

```python
# One-off query - use raw SQL
results = await db.q("""
    SELECT u.name, COUNT(p.id) as post_count
    FROM user u LEFT JOIN post p ON u.id = p.user_id
    GROUP BY u.id
""")
```

See [Best Practices: Using Views for Joins and CTEs](best-practices.md#using-views-for-joins-and-ctes) for more patterns.

### Replace Existing Views

```python
# Create view
view = await db.create_view("my_view", "SELECT * FROM users")

# Replace it with new SQL
view = await db.create_view(
    "my_view",
    "SELECT id, name FROM users",
    replace=True
)
```

### Query Operations on Views

```python
# Create view
view = await db.create_view("user_view", "SELECT * FROM user")

# SELECT all
all_users = await view()

# SELECT with limit
limited = await view(limit=10)

# GET by first column (pseudo-PK)
user = await view[1]  # Uses first column (id) as key

# LOOKUP
found = await view.lookup(email="alice@example.com")

# with_pk parameter works
results = await view(with_pk=True)
for pk, record in results:
    print(f"PK={pk}: {record}")
```

### Read-Only Enforcement

```python
view = await db.create_view("user_view", "SELECT * FROM user")

# Write operations are blocked
try:
    await view.insert({"name": "Alice"})
except NotImplementedError:
    print("Cannot insert into a view")

try:
    await view.update({"id": 1, "name": "Updated"})
except NotImplementedError:
    print("Cannot update a view")

try:
    await view.delete(1)
except NotImplementedError:
    print("Cannot delete from a view")

try:
    await view.upsert({"name": "Alice"})
except NotImplementedError:
    print("Cannot upsert into a view")
```

### Dynamic View Access

```python
# After creating view, access via db.v
active_users = await db.create_view("active_users", "SELECT * FROM user WHERE active = 1")

# Access by attribute
view = db.v.active_users  # Sync cache access

# Access by index
view = db.v['active_users']

# Multiple views
active, inactive = db.v['active_users', 'inactive_users']
```

### Reflect Existing Views

```python
# Create view with raw SQL
await db.q("CREATE VIEW user_names AS SELECT id, name FROM user")

# Reflect the view
view = await db.reflect_view('user_names')

# Now accessible via db.v
view = db.v.user_names  # Cache hit

# Query it
results = await view()
```

### Views with Dataclass Support

```python
# Create view
view = await db.create_view("user_view", "SELECT * FROM user")

# Enable dataclass mode
UserViewDC = view.dataclass()

# Queries return dataclass instances
results = await view()
for user in results:
    print(user.name)  # Type-safe field access
    print(user.email)
```

### Drop Views

```python
view = await db.create_view("temp_view", "SELECT * FROM user")

# Drop the view
await view.drop()

# View is now gone - can create again
view = await db.create_view("temp_view", "SELECT * FROM user")
```

### Complete Views Example

```python
from deebase import Database

db = Database("sqlite+aiosqlite:///myapp.db")

# Create tables
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
await users.insert({"name": "Bob", "status": "inactive"})
await orders.insert({"user_id": 1, "total": 99.99, "status": "completed"})
await orders.insert({"user_id": 1, "total": 149.99, "status": "pending"})

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
print(f"Active users: {len(active)}")

completed = await completed_orders()
print(f"Completed orders: {len(completed)}")

user_order_data = await user_orders()
for row in user_order_data:
    print(f"{row['name']}: ${row['total']} ({row['status']})")

# Access via db.v
view = db.v.active_users
results = await view()
```

### Testing

- **19 new Phase 7 tests** - All passing ✅
- **161 total tests** (Phases 1-7) - All passing ✅
- Comprehensive coverage:
  - View creation (simple, JOIN, aggregation)
  - View querying (SELECT, GET, LOOKUP)
  - Read-only enforcement
  - View reflection
  - Dynamic access via db.v
  - Dataclass support
  - View dropping

---

## Phase 8: Polish & Utilities ✅ COMPLETE

Phase 8 focuses on production-ready error handling, code generation utilities, and comprehensive documentation.

### Enhanced Exception System

DeeBase now has a comprehensive exception hierarchy for better error handling:

```python
from deebase import (
    DeeBaseError,          # Base exception
    NotFoundError,         # Record not found
    IntegrityError,        # Constraint violations
    ConnectionError,       # Database connection issues
    InvalidOperationError, # Invalid operations (e.g., writing to views)
    ValidationError,       # Data validation failures
    SchemaError,           # Schema-related errors
)
```

#### Exception Attributes

All exceptions include rich context:

```python
try:
    user = await users[999]
except NotFoundError as e:
    print(e.message)      # "Record with PK 999 not found in table 'user'"
    print(e.table_name)   # "user"
    print(e.filters)      # {'id': 999}
```

#### NotFoundError

Raised when a query returns no results.

**Attributes:**
- `message` (str): Error message
- `table_name` (str): Table name
- `filters` (dict): Filters that were applied

**Example:**
```python
from deebase import NotFoundError

try:
    user = await users.lookup(email="unknown@example.com")
except NotFoundError as e:
    print(f"Not found in {e.table_name}")
    print(f"Filters: {e.filters}")
    # Not found in user
    # Filters: {'email': 'unknown@example.com'}
```

#### IntegrityError

Raised when database constraints are violated (unique, foreign key, primary key).

**Attributes:**
- `message` (str): Error message
- `constraint` (str): Constraint type ('unique', 'primary_key', 'foreign_key')
- `table_name` (str): Table name

**Example:**
```python
from deebase import IntegrityError

class User:
    id: int
    email: str

users = await db.create(User, pk='id')

# Create unique constraint
await db.q("CREATE UNIQUE INDEX idx_email ON user(email)")

try:
    await users.insert({"id": 1, "email": "alice@example.com"})
    await users.insert({"id": 2, "email": "alice@example.com"})  # Duplicate!
except IntegrityError as e:
    print(f"Constraint {e.constraint} violated in {e.table_name}")
    # Constraint unique violated in user
```

#### ValidationError

Raised when input validation fails.

**Attributes:**
- `message` (str): Error message
- `field` (str): Field name that failed validation
- `value`: Invalid value

**Example:**
```python
from deebase import ValidationError

try:
    # Missing primary key
    await users.update({"name": "Alice"})
except ValidationError as e:
    print(f"Invalid {e.field}: {e.value}")
    # Invalid id: None

# xtra filter violations
admin_users = users.xtra(role="admin")
try:
    await admin_users.insert({"role": "user", "name": "Bob"})
except ValidationError as e:
    print(e.message)
    # Cannot insert into table 'user': role=user violates filter role=admin
```

#### SchemaError

Raised for schema-related errors (column not found, table not found).

**Attributes:**
- `message` (str): Error message
- `table_name` (str): Table name
- `column_name` (str): Column name

**Example:**
```python
from deebase import SchemaError

try:
    await users.lookup(unknown_column="value")
except SchemaError as e:
    print(f"Column {e.column_name} not found in {e.table_name}")
    # Column unknown_column not found in user

# Invalid primary key specification
class Product:
    id: int
    name: str

try:
    await db.create(Product, pk='product_id')  # Wrong PK name
except SchemaError as e:
    print(e.message)
    # Primary key column 'product_id' not found in class Product annotations
```

#### ConnectionError

Raised when database connection fails.

**Attributes:**
- `message` (str): Error message
- `database_url` (str): Sanitized database URL (password removed)

**Example:**
```python
from deebase import ConnectionError

try:
    db = Database("sqlite+aiosqlite:///nonexistent/path/db.db")
    await db.q("SELECT 1")
except ConnectionError as e:
    print(f"Failed to connect to {e.database_url}")
```

#### InvalidOperationError

Raised when an invalid operation is attempted (e.g., writing to a read-only view).

**Attributes:**
- `message` (str): Error message
- `operation` (str): Operation name
- `target` (str): Target object name

**Example:**
```python
from deebase import InvalidOperationError

view = await db.create_view("active_users", "SELECT * FROM user WHERE active = 1")

try:
    await view.insert({"name": "Alice"})
except InvalidOperationError as e:
    print(f"Cannot {e.operation} on {e.target}")
    # Cannot insert on view 'active_users'
```

### Error Handling Best Practices

```python
from deebase import (
    Database,
    NotFoundError,
    IntegrityError,
    ValidationError,
    SchemaError,
)

db = Database("sqlite+aiosqlite:///myapp.db")

class User:
    id: int
    email: str
    name: str

users = await db.create(User, pk='id')

# Handle specific exceptions
async def get_or_create_user(email: str, name: str):
    try:
        return await users.lookup(email=email)
    except NotFoundError:
        # User doesn't exist, create it
        try:
            return await users.insert({"email": email, "name": name})
        except IntegrityError as e:
            # Another process created it between lookup and insert
            print(f"Race condition: {e.message}")
            return await users.lookup(email=email)

# Validate input before operations
async def update_user_safe(user_id: int, updates: dict):
    try:
        user = await users[user_id]
    except NotFoundError:
        return {"error": "User not found"}

    try:
        user.update(updates)
        return await users.update(user)
    except ValidationError as e:
        return {"error": f"Invalid {e.field}: {e.value}"}
    except IntegrityError as e:
        return {"error": f"Constraint violation: {e.constraint}"}

# Handle schema errors gracefully
async def safe_lookup(**filters):
    try:
        return await users.lookup(**filters)
    except SchemaError as e:
        print(f"Unknown column: {e.column_name}")
        return None
    except NotFoundError:
        return None
```

### Dataclass Export Utilities

Phase 8 adds powerful utilities for generating Python code from database schemas.

#### dataclass_src()

Generate Python source code from a dataclass:

```python
from deebase import Database, dataclass_src

db = Database("sqlite+aiosqlite:///:memory:")

class User:
    id: int
    name: str
    email: str
    created_at: datetime

users = await db.create(User, pk='id')

# Generate dataclass
UserDC = users.dataclass()

# Get source code
src = dataclass_src(UserDC)
print(src)
```

**Output:**
```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    id: Optional[int] = None
    name: Optional[str] = None
    email: Optional[str] = None
    created_at: Optional[datetime] = None
```

#### create_mod()

Export multiple dataclasses to a Python module file:

```python
from deebase import create_mod

# Generate dataclasses from tables
UserDC = users.dataclass()
PostDC = posts.dataclass()
CommentDC = comments.dataclass()

# Export to models.py
create_mod(
    "models.py",
    UserDC,
    PostDC,
    CommentDC,
    overwrite=True
)
```

**Generated models.py:**
```python
"""Auto-generated dataclass models from DeeBase."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    id: Optional[int] = None
    name: Optional[str] = None
    email: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class Post:
    id: Optional[int] = None
    user_id: Optional[int] = None
    title: Optional[str] = None
    content: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class Comment:
    id: Optional[int] = None
    post_id: Optional[int] = None
    user_id: Optional[int] = None
    text: Optional[str] = None
    created_at: Optional[datetime] = None
```

#### create_mod_from_tables()

Convenience function to export directly from tables:

```python
from deebase import create_mod_from_tables

# Connect to existing database
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

# Now you can use the generated models
# from models import User, Post, Comment
```

### Complete Example with Error Handling

```python
from deebase import (
    Database,
    NotFoundError,
    IntegrityError,
    ValidationError,
    Text,
)
from datetime import datetime

db = Database("sqlite+aiosqlite:///blog.db")

# Define schema
class User:
    id: int
    username: str
    email: str
    created_at: datetime

class Post:
    id: int
    user_id: int
    title: str
    content: Text
    published: bool
    created_at: datetime

# Create tables
users = await db.create(User, pk='id')
posts = await db.create(Post, pk='id')

# Add unique constraint
await db.q("CREATE UNIQUE INDEX idx_username ON user(username)")
await db.q("CREATE UNIQUE INDEX idx_email ON user(email)")

# Safe user creation with error handling
async def create_user(username: str, email: str):
    try:
        user = await users.insert({
            "username": username,
            "email": email,
            "created_at": datetime.now()
        })
        print(f"Created user: {user['username']}")
        return user
    except IntegrityError as e:
        if e.constraint == "unique":
            print(f"Username or email already exists")
            return None
    except ValidationError as e:
        print(f"Invalid {e.field}: {e.value}")
        return None

# Safe post creation
async def create_post(user_id: int, title: str, content: str):
    try:
        # Verify user exists
        user = await users[user_id]

        post = await posts.insert({
            "user_id": user_id,
            "title": title,
            "content": content,
            "published": False,
            "created_at": datetime.now()
        })
        print(f"Created post: {post['title']}")
        return post
    except NotFoundError as e:
        print(f"User {user_id} not found")
        return None

# Safe query with error handling
async def get_user_posts(username: str):
    try:
        user = await users.lookup(username=username)
        user_posts = posts.xtra(user_id=user['id'])
        return await user_posts()
    except NotFoundError:
        print(f"User '{username}' not found")
        return []

# Test it
alice = await create_user("alice", "alice@example.com")
if alice:
    await create_post(alice['id'], "First Post", "Hello, world!")

bob = await create_user("bob", "alice@example.com")  # Duplicate email
# Output: Username or email already exists

alice_posts = await get_user_posts("alice")
print(f"Alice has {len(alice_posts)} posts")

await db.close()
```

### Documentation

Phase 8 includes comprehensive documentation:

#### API Reference
Complete API documentation for all classes, methods, and utilities:
- See `docs/api_reference.md`

#### Migration Guide
Guide for migrating from fastlite to DeeBase:
- See `docs/migrating_from_fastlite.md`

### Testing

- **161 total tests** (Phases 1-8) - All passing ✅
- Updated tests to use new exception types
- No regressions from error handling improvements

---

## Phase 9: Transaction Support ✅ COMPLETE

Phase 9 adds explicit transaction support for multi-operation atomicity, enabling safe batch operations and complex workflows.

### Transaction Context Manager

**What it does:**
Provides explicit transaction boundaries for multiple database operations that must succeed or fail together.

```python
from deebase import Database

db = Database("sqlite+aiosqlite:///myapp.db")

class User:
    id: int
    name: str
    balance: float

users = await db.create(User, pk='id')

# All operations inside transaction() commit together
async with db.transaction():
    # Multiple operations in one transaction
    alice = await users.insert({"name": "Alice", "balance": 100.0})
    bob = await users.insert({"name": "Bob", "balance": 50.0})

    # Transfer money
    alice['balance'] -= 25.0
    bob['balance'] += 25.0

    await users.update(alice)
    await users.update(bob)

# Transaction commits here - all changes saved atomically
```

**Key features:**
- Automatic commit on success
- Automatic rollback on exception
- All CRUD operations participate automatically
- Backward compatible - no code changes required

### Automatic Rollback on Error

```python
from deebase import IntegrityError

async with db.transaction():
    # First operation succeeds
    user1 = await users.insert({"name": "Charlie", "balance": 100.0})

    # Second operation fails (duplicate constraint, etc.)
    try:
        user2 = await users.insert({"id": user1['id'], "name": "Dave", "balance": 50.0})
    except IntegrityError:
        pass  # Error triggers rollback

# ROLLBACK executed automatically
# Database unchanged - neither user created
```

### Read-Modify-Write Pattern

```python
# Safe read-modify-write with transaction
async with db.transaction():
    # Read current state
    user = await users[1]

    # Modify
    user['balance'] += 100.0

    # Write back
    await users.update(user)

# Atomic update - no race conditions
```

### Money Transfer Example

```python
async def transfer_money(from_user_id: int, to_user_id: int, amount: float):
    """Transfer money between users atomically."""
    async with db.transaction():
        # Get both users
        sender = await users[from_user_id]
        receiver = await users[to_user_id]

        # Validate
        if sender['balance'] < amount:
            raise ValueError("Insufficient funds")

        # Update balances
        sender['balance'] -= amount
        receiver['balance'] += amount

        # Save both changes
        await users.update(sender)
        await users.update(receiver)

    # Both updates commit together
    # If any operation fails, both rollback

# Use it
try:
    await transfer_money(from_user_id=1, to_user_id=2, amount=50.0)
    print("Transfer successful")
except ValueError as e:
    print(f"Transfer failed: {e}")
```

### Batch Operations with Transactions

```python
# Insert multiple related records atomically
async with db.transaction():
    # Create user
    user = await users.insert({"name": "Eve", "balance": 1000.0})

    # Create related records
    for i in range(10):
        await posts.insert({
            "user_id": user['id'],
            "title": f"Post {i}",
            "content": f"Content {i}"
        })

# All or nothing - if any post fails, user creation rolls back too
```

### Nested Operations

```python
class Account:
    id: int
    user_id: int
    balance: float

accounts = await db.create(Account, pk='id')

# Transaction spans multiple tables
async with db.transaction():
    # Update user
    user = await users[1]
    user['balance'] += 500.0
    await users.update(user)

    # Update account
    account = await accounts.lookup(user_id=user['id'])
    account['balance'] += 500.0
    await accounts.update(account)

# Both tables updated atomically
```

### Backward Compatibility

**Important:** Transaction support is **fully backward compatible**. Existing code continues to work without changes.

```python
# Without transactions (still works - each operation auto-commits)
user = await users.insert({"name": "Frank", "balance": 100.0})
await users.update(user)

# With transactions (explicit control)
async with db.transaction():
    user = await users.insert({"name": "Grace", "balance": 200.0})
    await users.update(user)
```

### When to Use Transactions

**Use transactions when:**
- Multiple operations must succeed or fail together (atomicity)
- Transferring data between records (money transfers, inventory moves)
- Creating related records across tables (user + profile)
- Batch operations where partial success is unacceptable
- Read-modify-write operations (prevent race conditions)

**Don't use transactions for:**
- Single operations (each operation is already atomic)
- Read-only queries (no benefit)
- DDL operations (CREATE TABLE, ALTER TABLE, etc.)
- Long-running operations (hold locks minimally)

### Complete Example: E-commerce Order

```python
from deebase import Database, NotFoundError
from datetime import datetime

db = Database("sqlite+aiosqlite:///shop.db")

class Product:
    id: int
    name: str
    stock: int
    price: float

class Order:
    id: int
    user_id: int
    total: float
    created_at: datetime

class OrderItem:
    id: int
    order_id: int
    product_id: int
    quantity: int
    price: float

products = await db.create(Product, pk='id')
orders = await db.create(Order, pk='id')
order_items = await db.create(OrderItem, pk='id')

async def create_order(user_id: int, items: list[dict]):
    """Create order with multiple items atomically."""
    async with db.transaction():
        # Calculate total and validate stock
        total = 0.0
        for item in items:
            product = await products[item['product_id']]

            if product['stock'] < item['quantity']:
                raise ValueError(f"Insufficient stock for {product['name']}")

            total += product['price'] * item['quantity']

        # Create order
        order = await orders.insert({
            "user_id": user_id,
            "total": total,
            "created_at": datetime.now()
        })

        # Create order items and update stock
        for item in items:
            # Create order item
            await order_items.insert({
                "order_id": order['id'],
                "product_id": item['product_id'],
                "quantity": item['quantity'],
                "price": item['price']
            })

            # Decrement stock
            product = await products[item['product_id']]
            product['stock'] -= item['quantity']
            await products.update(product)

        return order

    # All changes commit together
    # If any step fails, everything rolls back

# Use it
try:
    order = await create_order(
        user_id=1,
        items=[
            {"product_id": 1, "quantity": 2, "price": 9.99},
            {"product_id": 2, "quantity": 1, "price": 19.99}
        ]
    )
    print(f"Order {order['id']} created successfully")
except ValueError as e:
    print(f"Order failed: {e}")
```

### Testing

- **22 new Phase 9 tests** - All passing ✅
- **183 total tests** (Phases 1-9) - All passing ✅
- Comprehensive coverage:
  - Basic transaction commit/rollback
  - Nested operations across tables
  - Error handling and rollback
  - Backward compatibility
  - Race condition prevention
  - Complex multi-table scenarios

---

## Phase 10: Foreign Keys & Defaults ✅ COMPLETE

Phase 10 enhances the `create()` method with foreign key support and automatic default value extraction.

### Foreign Keys with ForeignKey Type

Define foreign key relationships using the `ForeignKey` type annotation:

```python
from deebase import Database, ForeignKey, Text

# Parent table
class User:
    id: int
    name: str
    email: str

# Child table with FK
class Post:
    id: int
    title: str
    content: Text
    author_id: ForeignKey[int, "user"]  # FK to user.id

db = Database("sqlite+aiosqlite:///:memory:")
users = await db.create(User, pk='id')
posts = await db.create(Post, pk='id')

# Insert parent first
await users.insert({"id": 1, "name": "Alice", "email": "alice@example.com"})

# Insert child with valid FK
await posts.insert({"id": 1, "title": "Hello", "content": "...", "author_id": 1})
```

#### Explicit Column Reference

By default, `ForeignKey[T, "table"]` references `table.id`. You can specify a different column:

```python
class Article:
    id: int
    category_slug: ForeignKey[str, "category.slug"]  # FK to category.slug
```

#### Multiple Foreign Keys

```python
class BlogPost:
    id: int
    title: str
    author_id: ForeignKey[int, "user"]
    category_id: ForeignKey[int, "category"]
```

### Default Values from Class Definitions

DeeBase automatically extracts default values from class definitions:

```python
class Article:
    id: int
    title: str
    status: str = "draft"      # SQL DEFAULT 'draft'
    views: int = 0             # SQL DEFAULT 0
    featured: bool = False     # SQL DEFAULT 0

articles = await db.create(Article, pk='id')

# Insert without specifying defaults
article = await articles.insert({"id": 1, "title": "Hello"})
print(article["status"])    # "draft" (from default)
print(article["views"])     # 0 (from default)
print(article["featured"])  # False (from default)
```

#### Works with Dataclasses

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class Product:
    id: Optional[int] = None
    name: str = ""
    price: float = 0.0
    in_stock: bool = True
    category: str = "general"

products = await db.create(Product, pk='id')

# Returns dataclass instances with defaults applied
product = await products.insert({"name": "Widget"})
print(product.price)      # 0.0
print(product.in_stock)   # True
print(product.category)   # "general"
```

#### What Gets Extracted

| Type | Example | SQL Default |
|------|---------|-------------|
| `str` | `status: str = "draft"` | `DEFAULT 'draft'` |
| `int` | `views: int = 0` | `DEFAULT 0` |
| `float` | `price: float = 9.99` | `DEFAULT 9.99` |
| `bool` | `active: bool = True` | `DEFAULT 1` |

**Skipped (not extracted):**
- `dict = {}` - Mutable defaults
- `list = []` - Mutable defaults
- `field(default_factory=...)` - Default factories
- `None` - Indicates nullable, not a default

### if_not_exists Parameter

Create tables safely without error if they already exist:

```python
# First creation
users = await db.create(User, pk='id')
await users.insert({"id": 1, "name": "Alice"})

# Second creation - no error, data preserved
users = await db.create(User, pk='id', if_not_exists=True)
all_users = await users()  # [{"id": 1, "name": "Alice"}]
```

### replace Parameter

Drop and recreate tables:

```python
# Create with data
users = await db.create(User, pk='id')
await users.insert({"id": 1, "name": "Alice"})

# Replace - drops and recreates
users = await db.create(User, pk='id', replace=True)
all_users = await users()  # [] (table was dropped and recreated)
```

### FK Constraint Enforcement

SQLite requires explicit FK enforcement:

```python
from deebase import IntegrityError

# Enable FK constraints
await db.q("PRAGMA foreign_keys = ON")

# Now invalid FKs raise IntegrityError
try:
    await posts.insert({"id": 1, "title": "Test", "author_id": 999})
except IntegrityError as e:
    print("FK constraint violated!")
```

### Complete Example

```python
from deebase import Database, ForeignKey, Text, IntegrityError
from dataclasses import dataclass
from typing import Optional

# Parent tables
class Author:
    id: int
    name: str
    active: bool = True

class Category:
    id: int
    name: str
    slug: str

# Child table with multiple FKs and defaults
class Article:
    id: int
    title: str
    content: Text
    author_id: ForeignKey[int, "author"]
    category_id: ForeignKey[int, "category"]
    status: str = "draft"
    views: int = 0

async def main():
    db = Database("sqlite+aiosqlite:///:memory:")

    # Create tables (safe with if_not_exists)
    authors = await db.create(Author, pk='id', if_not_exists=True)
    categories = await db.create(Category, pk='id', if_not_exists=True)
    articles = await db.create(Article, pk='id', if_not_exists=True)

    # Enable FK enforcement
    await db.q("PRAGMA foreign_keys = ON")

    # Insert parent records
    await authors.insert({"id": 1, "name": "Alice"})
    await categories.insert({"id": 1, "name": "Tech", "slug": "tech"})

    # Insert article with FK references and defaults
    article = await articles.insert({
        "id": 1,
        "title": "Python Tips",
        "content": "Long article content...",
        "author_id": 1,
        "category_id": 1
        # status and views use defaults
    })

    print(article["status"])  # "draft"
    print(article["views"])   # 0

    await db.close()
```

### Testing

- **36 new Phase 10 tests** - All passing ✅
- **219 total tests** (Phases 1-10) - All passing ✅
- Coverage:
  - ForeignKey type parsing
  - FK constraint creation and enforcement
  - Default value extraction (str, int, float, bool)
  - Mutable defaults correctly skipped
  - if_not_exists behavior
  - replace behavior
  - Input/output type preservation

---

## Phase 11: FK Relationship Navigation ✅ COMPLETE

Phase 11 adds foreign key navigation for traversing relationships between tables.

### FK Metadata Property

Check what foreign keys a table has:

```python
from deebase import Database, ForeignKey

class Author:
    id: int
    name: str

class Post:
    id: int
    author_id: ForeignKey[int, "author"]
    title: str

db = Database("sqlite+aiosqlite:///:memory:")
authors = await db.create(Author, pk='id')
posts = await db.create(Post, pk='id')

# Check FK metadata
print(posts.foreign_keys)
# [{'column': 'author_id', 'references': 'author.id'}]

# Tables without FKs have empty list
print(authors.foreign_keys)
# []
```

### Convenience API: table.fk

Navigate to parent records with clean syntax:

```python
# Insert data
alice = await authors.insert({"name": "Alice"})
post = await posts.insert({
    "author_id": alice["id"],
    "title": "Intro to Python"
})

# Navigate to parent using FK accessor
author = await posts.fk.author_id(post)
print(author["name"])  # "Alice"
```

The `fk` accessor provides clean, intuitive syntax for forward FK navigation.

### Power User API: get_parent()

For more explicit control, use `get_parent()`:

```python
# Same result, more explicit
author = await posts.get_parent(post, "author_id")
print(author["name"])  # "Alice"
```

**When to use `get_parent()`:**
- Building generic code where FK column is dynamic
- When you want explicit control over FK navigation
- In error handling scenarios

### Reverse Navigation: get_children()

Find all records that reference a parent:

```python
# Get all posts by an author
author = await authors[1]
author_posts = await authors.get_children(author, "post", "author_id")

print(f"Author has {len(author_posts)} posts")
for p in author_posts:
    print(f"  - {p['title']}")
```

**Accepts string or Table object:**
```python
# String table name
author_posts = await authors.get_children(author, "post", "author_id")

# Or Table object
author_posts = await authors.get_children(author, posts, "author_id")
```

### Return Values

**`get_parent()` returns:**
- Parent record (dict or dataclass) if found
- `None` if FK value is `None` (nullable FK)
- `None` if parent not found (dangling FK)

**`get_children()` returns:**
- List of child records (may be empty)

```python
# Nullable FK handling
post_with_no_author = await posts.insert({
    "author_id": None,  # Nullable FK
    "title": "Anonymous Post"
})
author = await posts.get_parent(post_with_no_author, "author_id")
print(author)  # None

# Empty children list
new_author = await authors.insert({"name": "Bob"})
bob_posts = await authors.get_children(new_author, "post", "author_id")
print(bob_posts)  # [] (empty list)
```

### Dataclass Support

FK navigation respects the target table's dataclass setting:

```python
# Enable dataclass on authors
AuthorDC = authors.dataclass()

# Now get_parent returns dataclass instances
post = await posts[1]
author = await posts.get_parent(post, "author_id")

print(type(author))  # <class 'Author'>
print(author.name)   # Field access works!
```

### Chaining Navigation

Navigate across multiple relationships:

```python
class Comment:
    id: int
    post_id: ForeignKey[int, "post"]
    author_id: ForeignKey[int, "author"]
    content: str

comments = await db.create(Comment, pk='id')

# Navigate: comment -> post -> author
comment = await comments[1]
post = await comments.get_parent(comment, "post_id")
post_author = await posts.get_parent(post, "author_id")

print(f"Comment on '{post['title']}' by {post_author['name']}")
```

### Error Handling

```python
from deebase import ValidationError, SchemaError

# Invalid FK column
try:
    await posts.get_parent(post, "invalid_column")
except ValidationError as e:
    print(f"Column {e.field} not found")

# Non-FK column
try:
    await posts.get_parent(post, "title")  # title is not an FK
except ValidationError as e:
    print(f"{e.field} is not a foreign key")

# Child table not in cache
try:
    await authors.get_children(author, "nonexistent_table", "author_id")
except SchemaError as e:
    print(f"Table {e.table_name} not found")
```

### Works with Reflected Tables

FK navigation also works with tables reflected from the database:

```python
# Create tables with raw SQL
await db.q("""
    CREATE TABLE parent (id INTEGER PRIMARY KEY, name TEXT)
""")
await db.q("""
    CREATE TABLE child (
        id INTEGER PRIMARY KEY,
        parent_id INTEGER REFERENCES parent(id),
        value TEXT
    )
""")

# Reflect tables
await db.reflect()

parent = db.t.parent
child = db.t.child

# FK metadata is extracted during reflection
print(child.foreign_keys)
# [{'column': 'parent_id', 'references': 'parent.id'}]

# Navigation works
parent_record = await parent.insert({"name": "Test"})
child_record = await child.insert({"parent_id": parent_record["id"], "value": "Hello"})

found_parent = await child.get_parent(child_record, "parent_id")
print(found_parent["name"])  # "Test"
```

### Complete Example

```python
from deebase import Database, ForeignKey, Text

db = Database("sqlite+aiosqlite:///:memory:")
await db.q("PRAGMA foreign_keys = ON")

# Define schema
class Author:
    id: int
    name: str
    email: str

class Category:
    id: int
    name: str

class Post:
    id: int
    author_id: ForeignKey[int, "author"]
    category_id: ForeignKey[int, "category"]
    title: str
    content: Text

class Comment:
    id: int
    post_id: ForeignKey[int, "post"]
    author_id: ForeignKey[int, "author"]
    content: str

# Create tables
authors = await db.create(Author, pk='id')
categories = await db.create(Category, pk='id')
posts = await db.create(Post, pk='id')
comments = await db.create(Comment, pk='id')

# Insert data
alice = await authors.insert({"name": "Alice", "email": "alice@example.com"})
bob = await authors.insert({"name": "Bob", "email": "bob@example.com"})
tech = await categories.insert({"name": "Technology"})

post = await posts.insert({
    "author_id": alice["id"],
    "category_id": tech["id"],
    "title": "Intro to Python",
    "content": "Python is great..."
})

comment = await comments.insert({
    "post_id": post["id"],
    "author_id": bob["id"],
    "content": "Great post!"
})

# Forward navigation (convenience API)
post_author = await posts.fk.author_id(post)
post_category = await posts.fk.category_id(post)
print(f"'{post['title']}' by {post_author['name']} in {post_category['name']}")

# Reverse navigation
alice_posts = await authors.get_children(alice, "post", "author_id")
print(f"Alice has {len(alice_posts)} posts")

post_comments = await posts.get_children(post, comments, "post_id")
print(f"Post has {len(post_comments)} comments")

# Chain navigation
for c in post_comments:
    comment_author = await comments.get_parent(c, "author_id")
    print(f"  Comment by {comment_author['name']}: {c['content']}")

await db.close()
```

### Testing

- **26 new Phase 11 tests** - All passing ✅
- **250 total tests** (Phases 1-11) - All passing ✅
- Coverage:
  - FK metadata from create() and reflection
  - fk accessor convenience API
  - get_parent() power user API
  - get_children() reverse navigation
  - Null FK handling
  - Dangling FK handling (returns None)
  - Dataclass integration
  - Error handling
  - xtra() filter preservation

---

## Phase 12: Indexes ✅ COMPLETE

Phase 12 adds support for explicit indexes on tables for query optimization.

### Index Class

```python
from deebase import Index

# Simple named index
idx = Index("idx_email", "email")

# Unique index
idx = Index("idx_email", "email", unique=True)

# Composite index (multiple columns)
idx = Index("idx_author_date", "author_id", "created_at")

# Composite unique index
idx = Index("idx_unique_combo", "col1", "col2", unique=True)
```

### Creating Tables with Indexes

```python
from deebase import Database, Index

db = Database("sqlite+aiosqlite:///:memory:")

class Article:
    id: int
    title: str
    slug: str
    author_id: int
    created_at: str

# Create table with indexes using different syntaxes
articles = await db.create(
    Article,
    pk='id',
    indexes=[
        "slug",                                    # Simple index (auto-named: ix_article_slug)
        ("author_id", "created_at"),               # Composite index (auto-named)
        Index("idx_title_unique", "title", unique=True),  # Named unique index
    ]
)
```

**Index Syntax Options:**
- `"column"` - Simple string for single-column index (auto-named as `ix_tablename_column`)
- `("col1", "col2")` - Tuple for composite index (auto-named as `ix_tablename_col1_col2`)
- `Index("name", "col")` - Index object for named index
- `Index("name", "col", unique=True)` - Named unique index
- `Index("name", "col1", "col2")` - Named composite index

### Adding Indexes After Table Creation

```python
# Create table without indexes
articles = await db.create(Article, pk='id')

# Add index later
await articles.create_index("title")  # Auto-named: ix_article_title

# Add unique index with custom name
await articles.create_index("slug", name="idx_article_slug", unique=True)

# Add composite index
await articles.create_index(["author_id", "created_at"], name="idx_author_date")
```

### Dropping Indexes

```python
# Drop an index by name
await articles.drop_index("idx_author_date")
```

### Listing Indexes

```python
# List all indexes on a table
for idx in articles.indexes:
    print(f"Name: {idx['name']}")
    print(f"Columns: {idx['columns']}")
    print(f"Unique: {idx['unique']}")

# Example output:
# Name: ix_article_slug
# Columns: ['slug']
# Unique: False
#
# Name: idx_title_unique
# Columns: ['title']
# Unique: True
```

### Unique Index Enforcement

```python
class User:
    id: int
    email: str

users = await db.create(
    User,
    pk='id',
    indexes=[Index("idx_email", "email", unique=True)]
)

# Insert first user
await users.insert({"id": 1, "email": "alice@example.com"})

# Duplicate email raises IntegrityError
try:
    await users.insert({"id": 2, "email": "alice@example.com"})
except IntegrityError:
    print("Duplicate email rejected!")
```

### Index Naming Convention

Auto-generated names follow the pattern: `ix_{tablename}_{column1}_{column2}...`

| Index Spec | Generated Name |
|------------|----------------|
| `"title"` | `ix_article_title` |
| `("author_id", "created_at")` | `ix_article_author_id_created_at` |
| `Index("custom", "col")` | `custom` (uses provided name) |

### Complete Example

```python
import asyncio
from deebase import Database, Index, IntegrityError

async def main():
    db = Database("sqlite+aiosqlite:///:memory:")

    class User:
        id: int
        name: str
        email: str
        status: str

    # Create table with indexes
    users = await db.create(
        User,
        pk='id',
        indexes=[
            "name",                                  # Simple index
            Index("idx_email", "email", unique=True),  # Unique index
            ("status", "name"),                      # Composite index
        ]
    )

    # List indexes
    print("Indexes on users table:")
    for idx in users.indexes:
        print(f"  {idx['name']}: {idx['columns']}")

    # Insert users
    await users.insert({"id": 1, "name": "Alice", "email": "alice@example.com", "status": "active"})
    await users.insert({"id": 2, "name": "Bob", "email": "bob@example.com", "status": "active"})

    # Queries on indexed columns use the index
    user = await users.lookup(email="alice@example.com")
    print(f"Found: {user['name']}")

    # Unique constraint enforced
    try:
        await users.insert({"id": 3, "name": "Charlie", "email": "alice@example.com", "status": "pending"})
    except IntegrityError:
        print("Duplicate email rejected!")

    # Add index after table creation
    await users.create_index("status", name="idx_status")
    print(f"Now have {len(users.indexes)} indexes")

    await db.close()

asyncio.run(main())
```

### Testing

- **30 new Phase 12 tests** - All passing ✅
- **280 total tests** (Phases 1-12) - All passing ✅
- Coverage:
  - Index class creation and validation
  - indexes parameter in db.create()
  - Simple, composite, and unique indexes
  - Auto-generated index names
  - table.create_index() method
  - table.drop_index() method
  - table.indexes property
  - Unique constraint enforcement
  - Invalid column handling
  - Integration with CRUD operations

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

---

## Summary

**All 12 Phases Complete! 🎉**

DeeBase is now feature-complete with:
- ✅ **Async/await support** - Modern Python async for FastAPI and other frameworks
- ✅ **Ergonomic API** - Simple, intuitive operations inspired by fastlite
- ✅ **Type safety** - Optional dataclass support for IDE autocomplete
- ✅ **Rich type system** - Text, JSON, ForeignKey, Index, datetime, Optional support
- ✅ **CRUD operations** - Complete database operations (insert, update, upsert, delete, select, lookup)
- ✅ **Foreign keys** - ForeignKey type annotation for relationships
- ✅ **FK Navigation** - Navigate relationships with `table.fk.column(record)` and `get_children()`
- ✅ **Default values** - Automatic extraction from class definitions
- ✅ **Dynamic access** - Access tables with `db.t.tablename` after reflection
- ✅ **Views support** - Read-only database views
- ✅ **Transactions** - Atomic multi-operation commits with automatic rollback
- ✅ **Indexes** - Explicit indexes for query optimization with `Index` class
- ✅ **Comprehensive error handling** - 6 specific exception types with rich context
- ✅ **Code generation** - Export database schemas as Python dataclasses
- ✅ **Complete documentation** - API reference, migration guide, examples
- ✅ **280 passing tests** - Comprehensive test coverage

**Ready for production use!**
