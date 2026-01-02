# DeeBase Best Practices & Design Decisions

This guide helps you make informed decisions when using DeeBase, explaining the consequences of different approaches and when to use each feature.

## Table of Contents

- [Dict vs Dataclass: Choosing Your Programming Style](#dict-vs-dataclass-choosing-your-programming-style)
- [Reflection: When and How](#reflection-when-and-how)
- [Table and View Creation Patterns](#table-and-view-creation-patterns)
- [Using Views for Joins and CTEs](#using-views-for-joins-and-ctes)
- [Foreign Keys and Relationships](#foreign-keys-and-relationships)
- [Default Values](#default-values)
- [Indexes](#indexes)
- [Maintaining Consistency](#maintaining-consistency)
- [Error Handling Strategy](#error-handling-strategy)
- [Performance Considerations](#performance-considerations)
- [Schema Evolution](#schema-evolution)
- [CLI vs Python API: Choosing Your Interface](#cli-vs-python-api-choosing-your-interface)

---

## Dict vs Dataclass: Choosing Your Programming Style

DeeBase supports two programming styles: dictionary-based and dataclass-based. Understanding when to use each is crucial for maintaining a consistent codebase.

### Dictionary-Based Operations (Default)

**When to use:**
- Quick scripts and prototypes
- Jupyter notebooks and REPLs
- Dynamic data where fields may vary
- Working with JSON-like data
- When you don't need type checking

**How it works:**
```python
users = await db.create(User, pk='id')

# All operations return dicts by default
user = await users.insert({"name": "Alice", "email": "alice@example.com"})
print(user['name'])  # Dictionary access

all_users = await users()
for u in all_users:
    print(u['name'])  # Each is a dict
```

**Characteristics:**
- ✅ Simple and flexible
- ✅ No setup required
- ✅ Easy to serialize to JSON
- ❌ No type checking
- ❌ No IDE autocomplete
- ❌ Typos in keys fail at runtime

### Dataclass-Based Operations

**When to use:**
- Production applications
- Large codebases with multiple developers
- When you want IDE autocomplete and type checking
- When you need clear contracts between functions
- Working with typed frameworks (FastAPI, etc.)

**How it works:**
```python
users = await db.create(User, pk='id')

# Enable dataclass mode
UserDC = users.dataclass()

# All operations now return dataclass instances
user = await users.insert(UserDC(name="Alice", email="alice@example.com"))
print(user.name)  # Attribute access with autocomplete

all_users = await users()
for u in all_users:
    print(u.name)  # Each is a UserDC instance
```

**Characteristics:**
- ✅ Type checking and IDE support
- ✅ Catches field typos at development time
- ✅ Self-documenting code
- ✅ Better refactoring support
- ❌ Requires calling `.dataclass()` first
- ❌ Slightly more verbose

### Making the Choice

**Use dicts when:**
- You're exploring data interactively
- The structure is dynamic or varies
- You're prototyping quickly
- You frequently convert to/from JSON

**Use dataclasses when:**
- You're building production applications
- Multiple developers work on the codebase
- You want compile-time guarantees
- The schema is well-defined and stable

### Mixed Usage: Consequences and Pitfalls

**⚠️ Warning:** Mixing dict and dataclass operations can lead to confusion!

```python
users = await db.create(User, pk='id')

# Insert returns dict (default)
user1 = await users.insert({"name": "Alice", "email": "alice@example.com"})
print(user1['name'])  # ✅ Works

# Enable dataclass mode
UserDC = users.dataclass()

# Now INSERT returns dataclass instances
user2 = await users.insert({"name": "Bob", "email": "bob@example.com"})
print(user2.name)  # ✅ Works
print(user2['name'])  # ❌ TypeError: 'User' object is not subscriptable

# SELECT also returns dataclass instances now
all_users = await users()
print(all_users[0].name)  # ✅ Works if you've called .dataclass()
print(all_users[0]['name'])  # ❌ Fails after .dataclass()
```

**The Rule:** Once you call `.dataclass()`, ALL operations on that table return dataclass instances.

---

## Reflection: When and How

Reflection is the process of loading existing database schema into DeeBase. Understanding when to reflect is essential for working with existing databases.

### Table Creation: No Reflection Needed

When you create a table with `db.create()`, it's **automatically cached**:

```python
# Create table - automatically cached
users = await db.create(User, pk='id')

# Immediately available via db.t
users_again = db.t.users  # ✅ Works immediately (sync, no await)
```

**When to use:** Creating new tables from Python classes.

**Reflection needed:** ❌ No

### Raw SQL Creation: Reflection Required

When you create tables with raw SQL, you must **explicitly reflect**:

```python
# Create with raw SQL
await db.q("CREATE TABLE products (id INT PRIMARY KEY, name TEXT)")

# NOT available yet
try:
    products = db.t.products  # ❌ AttributeError
except AttributeError:
    pass

# Reflect to load the table
await db.reflect_table('products')

# Now available
products = db.t.products  # ✅ Works
```

**When to use:** Working with tables created outside DeeBase.

**Reflection needed:** ✅ Yes - call `db.reflect_table(name)`

### Existing Databases: Bulk Reflection

When connecting to an existing database with many tables:

```python
# Connect to existing database
db = Database("sqlite+aiosqlite:///legacy.db")

# Reflect ALL tables at once
await db.reflect()

# All tables now available
users = db.t.users
posts = db.t.posts
comments = db.t.comments
```

**When to use:** Working with databases created by other tools or applications.

**Reflection needed:** ✅ Yes - call `db.reflect()`

### Views: Creation vs Reflection

#### View Creation: No Reflection Needed

```python
# Create view with DeeBase
view = await db.create_view(
    "active_users",
    "SELECT * FROM users WHERE active = 1"
)

# Immediately available
view_again = db.v.active_users  # ✅ Works immediately (sync, no await)
```

**When to use:** Creating new views from within your application.

**Reflection needed:** ❌ No

#### View Reflection: When Views Exist

```python
# View was created outside DeeBase (raw SQL, migration tool, etc.)
await db.q("CREATE VIEW user_emails AS SELECT id, name, email FROM users")

# NOT available yet
try:
    view = db.v.user_emails  # ❌ AttributeError
except AttributeError:
    pass

# Reflect to load the view
await db.reflect_view('user_emails')

# Now available
view = db.v.user_emails  # ✅ Works
```

**When to use:** Working with views created by raw SQL or external tools.

**Reflection needed:** ✅ Yes - call `db.reflect_view(name)`

### Reflection Decision Tree

```
Did you create the table/view with db.create() or db.create_view()?
├─ YES → No reflection needed, immediately available via db.t or db.v
└─ NO → Created with raw SQL or external tool?
    └─ YES → Reflection required
        ├─ Single table/view → await db.reflect_table(name) or await db.reflect_view(name)
        └─ Multiple tables → await db.reflect()
```

---

## Table and View Creation Patterns

### Pattern 1: Pure Python (Recommended for New Projects)

```python
from deebase import Database, ForeignKey, Text

# Define schema in Python with FKs and defaults
class User:
    id: int
    name: str
    email: str
    status: str = "active"  # Default value

class Post:
    id: int
    author_id: ForeignKey[int, "user"]  # FK to user.id
    title: str
    content: Text
    views: int = 0  # Default value

# Create tables (use if_not_exists for safety)
users = await db.create(User, pk='id', if_not_exists=True)
posts = await db.create(Post, pk='id', if_not_exists=True)

# Create views
popular_posts = await db.create_view(
    "popular_posts",
    "SELECT * FROM post WHERE views > 1000"
)

# Everything is immediately available
users = db.t.users
posts = db.t.posts
view = db.v.popular_posts
```

**Pros:**
- ✅ Type-safe schema definition
- ✅ Foreign keys via ForeignKey type
- ✅ Default values from class definitions
- ✅ No reflection needed
- ✅ Self-documenting
- ✅ Version controlled

**Cons:**
- ❌ Can't use advanced SQL features (CHECK constraints, triggers, etc.)
- ❌ Must match Python type system

### Pattern 2: Raw SQL + Reflection (For Complex Schemas)

```python
# Create with raw SQL for advanced features
await db.q("""
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CHECK (length(email) > 3)
    )
""")

# Reflect to load
await db.reflect_table('users')

# Now use Python API
users = db.t.users
await users.insert({"email": "alice@example.com"})
```

**Pros:**
- ✅ Full SQL features (CHECK, DEFAULT, triggers, etc.)
- ✅ Can use database-specific features
- ✅ Direct control over schema

**Cons:**
- ❌ Requires reflection step
- ❌ Schema not in Python code
- ❌ No type checking during table creation

### Pattern 3: Hybrid (Best of Both Worlds)

```python
# Use Python for simple tables
users = await db.create(User, pk='id')

# Use raw SQL for complex constraints
await db.q("""
    CREATE UNIQUE INDEX idx_email ON user(email)
""")
await db.q("""
    CREATE TRIGGER user_updated
    AFTER UPDATE ON user
    BEGIN
        UPDATE user SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END
""")
```

**Pros:**
- ✅ Python schema definition
- ✅ Advanced SQL when needed
- ✅ No reflection for base tables

**Cons:**
- ❌ Schema split between Python and SQL
- ❌ Requires understanding both approaches

---

## Using Views for Joins and CTEs

Views provide an elegant solution for working with JOINs and complex queries in DeeBase without adding a join API. This approach keeps the library simple while giving you full flexibility.

### The Key Insight

Views, JOINs, and CTEs all have something in common: they produce **result sets with column metadata**. DeeBase's `reflect_view()` discovers this metadata from the database, so you don't need a Python class definition. The database tells us the column structure.

### Pattern 1: Views for Repeated Joins

When you frequently query joined data, create a view:

```python
# Create tables
class User:
    id: int
    name: str
    email: str

class Post:
    id: int
    author_id: ForeignKey[int, "user"]
    title: str
    views: int

users = await db.create(User, pk='id')
posts = await db.create(Post, pk='id')

# Create a view for posts with author info
post_authors = await db.create_view(
    "post_authors",
    """
    SELECT p.id, p.title, p.views, u.name as author_name, u.email as author_email
    FROM post p
    JOIN user u ON p.author_id = u.id
    """
)

# Now use it like any table (read-only)
results = await post_authors()                          # All rows
results = await post_authors(limit=10)                  # With limit
result = await post_authors.lookup(author_name="Alice") # Filter
PostAuthorDC = post_authors.dataclass()                 # Type-safe access!
```

**Benefits:**
- ✅ Full DeeBase API (select, lookup, dataclass, xtra)
- ✅ Database handles the JOIN optimization
- ✅ No N+1 query problem
- ✅ Schema-less - no Python class needed

### Pattern 2: Raw SQL for One-Off Joins

For ad-hoc complex queries, use `db.q()` directly:

```python
# One-off join query
results = await db.q("""
    SELECT
        u.name,
        COUNT(p.id) as post_count,
        SUM(p.views) as total_views
    FROM user u
    LEFT JOIN post p ON u.id = p.author_id
    GROUP BY u.id
""")
# Returns: [{'name': 'Alice', 'post_count': 5, 'total_views': 1234}, ...]
```

**Use this for:**
- Complex aggregations
- One-time reports
- Ad-hoc analysis
- Queries that don't fit the view pattern

### Pattern 3: CTEs via Raw SQL

For recursive queries or complex CTEs, use `db.q()`:

```python
# Recursive CTE example (e.g., org chart)
results = await db.q("""
    WITH RECURSIVE org_tree AS (
        SELECT id, name, manager_id, 0 as level
        FROM employees
        WHERE manager_id IS NULL

        UNION ALL

        SELECT e.id, e.name, e.manager_id, ot.level + 1
        FROM employees e
        JOIN org_tree ot ON e.manager_id = ot.id
    )
    SELECT * FROM org_tree ORDER BY level, name
""")
```

### Pattern 4: Views for Complex Aggregations

Create views for dashboard-style aggregated data:

```python
# User stats view
await db.create_view(
    "user_stats",
    """
    SELECT
        u.id,
        u.name,
        COUNT(p.id) as total_posts,
        COALESCE(SUM(p.views), 0) as total_views,
        MAX(p.created_at) as last_post_date
    FROM user u
    LEFT JOIN post p ON u.id = p.author_id
    GROUP BY u.id, u.name
    """
)

# Use with full DeeBase API
stats_view = db.v.user_stats
all_stats = await stats_view()
top_users = await stats_view(limit=10)  # Note: would need ORDER BY in view

# Generate dataclass for type safety
UserStatsDC = stats_view.dataclass()
```

### When to Use Each Approach

| Scenario | Solution |
|----------|----------|
| Repeated join queries | Create a view with `db.create_view()` |
| One-off complex query | Use `db.q()` with raw SQL |
| Recursive queries (CTEs) | Use `db.q()` with raw SQL |
| Dashboard aggregations | Create a view |
| Bulk navigation (avoid N+1) | Create a view with JOIN |
| Simple FK traversal | Use `table.fk.column(record)` |

### Why Not a Join API?

DeeBase intentionally doesn't add a join API because:

1. **Views already solve it** - `db.create_view()` + view operations cover most use cases
2. **SQL is the right tool** - JOINs are a SQL concept; `db.q()` lets you write optimal SQL
3. **Simplicity** - Adding join builders adds complexity without much benefit
4. **Performance** - Views are optimized by the database; Python join builders can't match it

### Complete Example

```python
from deebase import Database, ForeignKey

db = Database("sqlite+aiosqlite:///:memory:")

# Tables
class Author:
    id: int
    name: str

class Book:
    id: int
    author_id: ForeignKey[int, "author"]
    title: str
    sales: int

authors = await db.create(Author, pk='id')
books = await db.create(Book, pk='id')

# Data
await authors.insert({"name": "Alice"})
await authors.insert({"name": "Bob"})
await books.insert({"author_id": 1, "title": "Python Guide", "sales": 1000})
await books.insert({"author_id": 1, "title": "Async Patterns", "sales": 500})
await books.insert({"author_id": 2, "title": "Data Science", "sales": 2000})

# View for joined data
await db.create_view(
    "book_details",
    """
    SELECT b.id, b.title, b.sales, a.name as author_name
    FROM book b JOIN author a ON b.author_id = a.id
    """
)

# Use the view
book_details = db.v.book_details
all_books = await book_details()
# [{'id': 1, 'title': 'Python Guide', 'sales': 1000, 'author_name': 'Alice'}, ...]

# With dataclass
BookDetailDC = book_details.dataclass()
typed_books = await book_details()
for book in typed_books:
    print(f"{book.title} by {book.author_name}: {book.sales} sales")

# One-off aggregation via db.q()
top_authors = await db.q("""
    SELECT a.name, SUM(b.sales) as total_sales
    FROM author a JOIN book b ON a.id = b.author_id
    GROUP BY a.id
    ORDER BY total_sales DESC
    LIMIT 5
""")
```

---

### Foreign Keys and Relationships

DeeBase supports foreign keys via the `ForeignKey` type annotation:

```python
from deebase import ForeignKey

class Post:
    id: int
    author_id: ForeignKey[int, "user"]       # FK to user.id
    category_id: ForeignKey[int, "category"]  # FK to category.id
```

**Best Practices:**

1. **Create parent tables first** - FK constraints require referenced tables to exist
   ```python
   users = await db.create(User, pk='id')
   posts = await db.create(Post, pk='id')  # After users
   ```

2. **Enable FK enforcement in SQLite** - By default, SQLite doesn't enforce FKs
   ```python
   await db.q("PRAGMA foreign_keys = ON")
   ```

3. **Use `if_not_exists` in production** - Safely handle restarted applications
   ```python
   users = await db.create(User, pk='id', if_not_exists=True)
   ```

4. **Reference explicit columns when needed** - Default is `table.id`
   ```python
   # FK to non-id column
   category_slug: ForeignKey[str, "category.slug"]
   ```

### FK Navigation

DeeBase provides two APIs for navigating FK relationships:

#### Convenience API: `table.fk.column(record)`

```python
# Navigate from post to author
post = await posts[1]
author = await posts.fk.author_id(post)
print(author['name'])
```

**Use this when:**
- FK column is known at coding time
- You want clean, readable syntax
- Following a single FK

#### Power User API: `get_parent()` and `get_children()`

```python
# Forward navigation
author = await posts.get_parent(post, "author_id")

# Reverse navigation
author_posts = await authors.get_children(author, "post", "author_id")
```

**Use this when:**
- FK column is dynamic (stored in variable)
- Building generic code
- Navigating in reverse direction

#### Navigation Best Practices

1. **Use convenience API for simple navigation**
   ```python
   # ✅ Clean and readable
   author = await posts.fk.author_id(post)

   # ❌ More verbose for simple cases
   author = await posts.get_parent(post, "author_id")
   ```

2. **Check for None returns** - FK navigation returns None for nullable FKs and dangling FKs
   ```python
   author = await posts.fk.author_id(post)
   if author:
       print(author['name'])
   else:
       print("No author found")
   ```

3. **Avoid N+1 queries** - Don't navigate FKs in loops for bulk data
   ```python
   # ❌ N+1 problem: one query per post
   posts = await posts_table()
   for post in posts:
       author = await posts_table.fk.author_id(post)  # N additional queries

   # ✅ Use JOIN for bulk data
   results = await db.q("""
       SELECT p.*, u.name as author_name
       FROM post p
       JOIN user u ON p.author_id = u.id
   """)
   ```

4. **Ensure referenced tables are cached** - Navigation requires target tables in cache
   ```python
   # ❌ Will fail if 'author' not in cache
   author = await posts.fk.author_id(post)

   # ✅ Ensure tables are cached first
   await db.reflect()  # Or create tables
   author = await posts.fk.author_id(post)
   ```

5. **Navigation respects dataclass settings** - Return type matches target table's configuration
   ```python
   # Enable dataclass on authors
   AuthorDC = authors.dataclass()

   # Navigation now returns AuthorDC
   author = await posts.fk.author_id(post)
   print(author.name)  # Field access works
   ```

### Default Values

Use Python class defaults for SQL DEFAULT values:

```python
class Article:
    id: int
    title: str
    status: str = "draft"     # SQL DEFAULT 'draft'
    views: int = 0            # SQL DEFAULT 0
    featured: bool = False    # SQL DEFAULT 0
```

**What works:**
- `str`, `int`, `float`, `bool` defaults → SQL DEFAULT clause

**What doesn't work (by design):**
- `dict = {}` - Mutable defaults skipped
- `list = []` - Mutable defaults skipped
- `field(default_factory=...)` - Factories skipped
- `None` - Means nullable, not a default

Mutable defaults still work Python-side when creating instances—they're just not stored as SQL defaults.

---

## Indexes

Indexes improve query performance on frequently accessed columns. DeeBase provides multiple ways to create and manage indexes.

### When to Create Indexes

**Create indexes on columns you:**
- Filter frequently (`WHERE column = value`)
- Sort by (`ORDER BY column`)
- Join on (`JOIN ... ON table.column = other.column`)
- Use in unique constraints (emails, slugs, usernames)

**Don't create indexes on:**
- Columns you rarely query
- Very small tables (< 1000 rows)
- Columns with low cardinality (boolean, status with 2-3 values)
- Every column (indexes have storage and write overhead)

### Index Creation Patterns

#### Pattern 1: Indexes at Table Creation (Recommended)

Define indexes when creating the table for the best visibility:

```python
from deebase import Index

class Article:
    id: int
    title: str
    slug: str
    author_id: int
    status: str
    created_at: str

articles = await db.create(
    Article,
    pk='id',
    indexes=[
        Index("idx_slug", "slug", unique=True),    # Unique for URL lookups
        ("author_id", "created_at"),               # Composite for author queries
        "status",                                   # Filter by status
    ]
)
```

**Benefits:**
- Schema and indexes defined together
- Version controlled with your code
- Easy to see all indexes at a glance

#### Pattern 2: Indexes After Creation

Add indexes to existing tables:

```python
# Table already exists
articles = db.t.articles

# Add indexes as needed
await articles.create_index("category_id")
await articles.create_index(["author_id", "published_at"], name="idx_author_published")
await articles.create_index("email", unique=True)
```

**Use this when:**
- Working with existing databases
- Adding indexes based on query analysis
- Schema is managed by migration tools

#### Pattern 3: Hybrid (Raw SQL for Advanced Indexes)

For partial indexes or expression indexes not supported by the `Index` class:

```python
# Create table with DeeBase
articles = await db.create(Article, pk='id')

# Add advanced index with raw SQL
await db.q("CREATE INDEX idx_published ON article(created_at) WHERE status = 'published'")
await db.q("CREATE INDEX idx_title_lower ON article(LOWER(title))")
```

### Index Naming Conventions

**Auto-generated names** follow the pattern `ix_{tablename}_{columns}`:

| Index Definition | Generated Name |
|------------------|----------------|
| `"slug"` | `ix_article_slug` |
| `("author_id", "created_at")` | `ix_article_author_id_created_at` |

**Named indexes** - Use clear, descriptive names:

```python
# ✅ Good names
Index("idx_user_email_unique", "email", unique=True)
Index("idx_post_author_date", "author_id", "created_at")

# ❌ Avoid generic names
Index("idx1", "email")
Index("index", "author_id")
```

### Unique Indexes vs Primary Keys

**Use unique indexes for:**
- Secondary unique columns (email, slug, username)
- Business-level uniqueness constraints

**Use primary keys for:**
- Record identification
- Foreign key relationships

```python
class User:
    id: int              # PK - for FK relationships
    email: str           # Unique index - business constraint
    username: str        # Unique index - business constraint

users = await db.create(
    User,
    pk='id',
    indexes=[
        Index("idx_email", "email", unique=True),
        Index("idx_username", "username", unique=True),
    ]
)
```

### Composite Index Order Matters

For composite indexes, **column order affects query optimization**:

```python
# Index on (author_id, created_at)
articles = await db.create(
    Article,
    pk='id',
    indexes=[("author_id", "created_at")]
)

# ✅ Uses the index
await articles.lookup(author_id=1)                      # First column
await articles.lookup(author_id=1, created_at="2024")  # Both columns

# ❌ Cannot use the index efficiently
await articles.lookup(created_at="2024")               # Second column only
```

**Rule:** Put the most selective (filtered) column first, or order by how you query.

### Listing and Managing Indexes

```python
# List all indexes
for idx in articles.indexes:
    print(f"{idx['name']}: {idx['columns']} (unique={idx['unique']})")

# Drop an index
await articles.drop_index("ix_article_status")
```

### Performance Trade-offs

**Indexes speed up reads but slow down writes:**

| Operation | Effect |
|-----------|--------|
| SELECT with WHERE | ✅ Faster |
| INSERT | ❌ Slower (must update index) |
| UPDATE | ❌ Slower (may update index) |
| DELETE | ❌ Slower (must update index) |

**Best practice:** Only index columns you actually query. Measure before and after adding indexes.

---

## Maintaining Consistency

### Dataclass Consistency Strategy

**Problem:** Once you call `.dataclass()` on a table, operations return dataclass instances. If you call it inconsistently, your code will have mixed types.

**Solution: Call `.dataclass()` immediately after table creation or reflection**

```python
# ✅ GOOD: Establish mode early
users = await db.create(User, pk='id')
UserDC = users.dataclass()  # Enable immediately

posts = await db.create(Post, pk='id')
PostDC = posts.dataclass()  # Enable immediately

# All subsequent operations are consistent
user = await users.insert(UserDC(...))  # Returns UserDC
users_list = await users()  # Returns List[UserDC]
```

```python
# ❌ BAD: Mixing dict and dataclass
users = await db.create(User, pk='id')

# Some operations with dicts
user1 = await users.insert({"name": "Alice"})  # Returns dict
print(user1['name'])  # Works

# Later, enable dataclass
UserDC = users.dataclass()

# Now operations return dataclass
user2 = await users.insert({"name": "Bob"})  # Returns UserDC
print(user2['name'])  # ❌ Fails! Need user2.name
```

### Recommended Initialization Pattern

```python
async def init_database():
    """Initialize database with consistent configuration."""
    db = Database("sqlite+aiosqlite:///myapp.db")

    # Create all tables
    users = await db.create(User, pk='id')
    posts = await db.create(Post, pk='id')
    comments = await db.create(Comment, pk='id')

    # Enable dataclass mode for all tables (if desired)
    UserDC = users.dataclass()
    PostDC = posts.dataclass()
    CommentDC = comments.dataclass()

    # Return configured database
    return db, (UserDC, PostDC, CommentDC)

# Use it
db, (UserDC, PostDC, CommentDC) = await init_database()

# All operations are now consistently typed
```

### Per-Module Consistency

If you're building a large application, maintain consistency per module:

```python
# users_module.py
class User:
    id: int
    name: str
    email: str

async def init_users(db):
    users = await db.create(User, pk='id')
    UserDC = users.dataclass()  # Always dataclass in this module
    return users, UserDC

# In application code
users, UserDC = await init_users(db)
# All user operations use UserDC
```

---

## Error Handling Strategy

### Exception Hierarchy

DeeBase provides specific exception types for different error scenarios:

```python
DeeBaseError (base)
├── NotFoundError (record not found)
├── IntegrityError (constraint violations)
├── ValidationError (data validation failures)
├── SchemaError (schema-related errors)
├── ConnectionError (database connection issues)
└── InvalidOperationError (invalid operations)
```

### When to Catch Which Exception

#### `NotFoundError`: Optional Records

**When to catch:** When a missing record is acceptable.

```python
# Pattern: Optional lookup
try:
    user = await users.lookup(email=email)
except NotFoundError:
    user = None

if user:
    print(f"Found: {user.name}")
else:
    print("User not found, creating new...")
    user = await users.insert({"email": email, "name": name})
```

**When NOT to catch:** When the record must exist (let it propagate).

#### `IntegrityError`: Constraint Violations

**When to catch:** When duplicates or constraint violations are possible.

```python
# Pattern: Handle duplicate gracefully
try:
    user = await users.insert({"email": email, "name": name})
except IntegrityError as e:
    if e.constraint == "unique":
        print(f"Email {email} already exists")
        user = await users.lookup(email=email)
    else:
        raise  # Re-raise other integrity errors
```

**When NOT to catch:** When constraints should never be violated (programming error).

#### `ValidationError`: Input Validation

**When to catch:** When processing user input.

```python
# Pattern: Validate user input
try:
    updated_user = await users.update(user_data)
except ValidationError as e:
    return {"error": f"Invalid {e.field}: {e.value}"}
```

**When NOT to catch:** When data comes from trusted internal sources.

#### `SchemaError`: Development vs Production

**When to catch:** Rarely - usually indicates a programming error.

```python
# Usually let it fail during development
user = await users.lookup(email=email)  # Typo causes SchemaError

# But can catch for dynamic queries
try:
    result = await users.lookup(**dynamic_filters)
except SchemaError as e:
    print(f"Invalid column: {e.column_name}")
    result = None
```

### Error Handling Patterns

#### Pattern 1: Get-or-Create with Race Condition Handling

```python
async def get_or_create_user(email: str, name: str):
    """Get existing user or create new one, handling race conditions."""
    try:
        # Try to find existing
        return await users.lookup(email=email)
    except NotFoundError:
        # Doesn't exist, create it
        try:
            return await users.insert({"email": email, "name": name})
        except IntegrityError:
            # Another process created it between lookup and insert
            # Try one more time
            return await users.lookup(email=email)
```

#### Pattern 2: Safe Update with Validation

```python
async def safe_update_user(user_id: int, updates: dict) -> dict:
    """Update user with comprehensive error handling."""
    try:
        # Verify user exists
        user = await users[user_id]

        # Apply updates
        user.update(updates)

        # Attempt update
        return {"success": True, "user": await users.update(user)}

    except NotFoundError:
        return {"success": False, "error": "User not found"}
    except ValidationError as e:
        return {"success": False, "error": f"Invalid {e.field}: {e.value}"}
    except IntegrityError as e:
        return {"success": False, "error": f"Constraint violated: {e.constraint}"}
```

#### Pattern 3: Bulk Operations with Error Collection

```python
async def bulk_insert_users(user_list: list[dict]) -> dict:
    """Insert multiple users, collecting errors."""
    results = {"success": [], "errors": []}

    for user_data in user_list:
        try:
            user = await users.insert(user_data)
            results["success"].append(user)
        except IntegrityError as e:
            results["errors"].append({
                "data": user_data,
                "error": f"Constraint {e.constraint} violated"
            })
        except ValidationError as e:
            results["errors"].append({
                "data": user_data,
                "error": f"Invalid {e.field}: {e.value}"
            })

    return results
```

---

## Transaction Management

Understanding when and how to use transactions is critical for data integrity and performance.

### When to Use Transactions

**Use transactions when:**

1. **Multi-operation atomicity** - All operations must succeed or fail together
   ```python
   async with db.transaction():
       user = await users.insert({"name": "Alice"})
       profile = await profiles.insert({"user_id": user['id']})
   # Both succeed or both fail
   ```

2. **Financial operations** - Money transfers, account balances
   ```python
   async with db.transaction():
       sender['balance'] -= amount
       receiver['balance'] += amount
       await accounts.update(sender)
       await accounts.update(receiver)
   ```

3. **Inventory management** - Stock updates, order fulfillment
   ```python
   async with db.transaction():
       product = await products[product_id]
       product['stock'] -= quantity
       await products.update(product)
       await orders.insert({"product_id": product_id, "quantity": quantity})
   ```

4. **Read-modify-write** - Prevent race conditions
   ```python
   async with db.transaction():
       counter = await counters[1]
       counter['value'] += 1
       await counters.update(counter)
   # Atomic increment - no lost updates
   ```

5. **Batch operations** - Create/update multiple related records
   ```python
   async with db.transaction():
       order = await orders.insert({"total": 0.0})
       for item in items:
           await order_items.insert({"order_id": order['id'], **item})
   ```

### When NOT to Use Transactions

**Avoid transactions for:**

1. **Single operations** - Each operation is already atomic
   ```python
   # ❌ Unnecessary transaction
   async with db.transaction():
       user = await users.insert({"name": "Bob"})

   # ✅ Single operation is already atomic
   user = await users.insert({"name": "Bob"})
   ```

2. **Read-only queries** - No benefit from transactions
   ```python
   # ❌ Unnecessary transaction
   async with db.transaction():
       users_list = await users()

   # ✅ Direct query
   users_list = await users()
   ```

3. **DDL operations** - CREATE TABLE, ALTER TABLE (not transactional in most databases)
   ```python
   # ❌ DDL not transactional
   async with db.transaction():
       await db.q("CREATE TABLE products (id INT)")

   # ✅ DDL outside transactions
   await db.q("CREATE TABLE products (id INT)")
   ```

4. **Long-running operations** - Hold locks minimally
   ```python
   # ❌ Long transaction holds locks
   async with db.transaction():
       for i in range(10000):
           await users.insert({"name": f"User {i}"})

   # ✅ Smaller batches or no transaction
   for i in range(10000):
       await users.insert({"name": f"User {i}"})
   ```

### Common Transaction Patterns

#### Pattern 1: Money Transfer (Atomic Update)

```python
async def transfer_money(from_id: int, to_id: int, amount: float):
    """Transfer money atomically between accounts."""
    async with db.transaction():
        # Get both accounts
        sender = await accounts[from_id]
        receiver = await accounts[to_id]

        # Validate
        if sender['balance'] < amount:
            raise ValueError("Insufficient funds")

        # Update both
        sender['balance'] -= amount
        receiver['balance'] += amount

        await accounts.update(sender)
        await accounts.update(receiver)

    # Commits together - both succeed or both fail
```

#### Pattern 2: Create with Related Records

```python
async def create_user_with_profile(user_data: dict, profile_data: dict):
    """Create user and profile atomically."""
    async with db.transaction():
        # Create user
        user = await users.insert(user_data)

        # Create profile with user_id
        profile_data['user_id'] = user['id']
        profile = await profiles.insert(profile_data)

        return user, profile

    # If profile creation fails, user creation rolls back
```

#### Pattern 3: Batch Insert with Validation

```python
async def create_order(order_data: dict, items: list[dict]):
    """Create order with items, validating stock."""
    async with db.transaction():
        # Validate all items have stock
        for item in items:
            product = await products[item['product_id']]
            if product['stock'] < item['quantity']:
                raise ValueError(f"Insufficient stock for {product['name']}")

        # Create order
        order = await orders.insert(order_data)

        # Create items and decrement stock
        for item in items:
            item['order_id'] = order['id']
            await order_items.insert(item)

            product = await products[item['product_id']]
            product['stock'] -= item['quantity']
            await products.update(product)

        return order

    # All or nothing - order, items, and stock updates
```

#### Pattern 4: Safe Counter Increment

```python
async def increment_counter(counter_id: int):
    """Atomically increment a counter."""
    async with db.transaction():
        counter = await counters[counter_id]
        counter['value'] += 1
        await counters.update(counter)
        return counter['value']

    # No lost updates - transaction prevents race conditions
```

### Error Handling in Transactions

```python
# Pattern: Catch specific errors, let transaction rollback
async def safe_transfer(from_id: int, to_id: int, amount: float) -> dict:
    try:
        async with db.transaction():
            sender = await accounts[from_id]
            receiver = await accounts[to_id]

            if sender['balance'] < amount:
                raise ValueError("Insufficient funds")

            sender['balance'] -= amount
            receiver['balance'] += amount

            await accounts.update(sender)
            await accounts.update(receiver)

        return {"success": True}

    except NotFoundError as e:
        return {"success": False, "error": f"Account not found: {e.table_name}"}
    except ValueError as e:
        return {"success": False, "error": str(e)}
    # Any exception causes automatic rollback
```

### Performance Considerations

**Transactions add overhead:**
- Locks held for transaction duration
- Rollback overhead on failure
- Database transaction log overhead

**Best practices:**
1. Keep transactions short
2. Don't do I/O inside transactions (API calls, file operations)
3. Don't use transactions for read-only operations
4. Consider optimistic locking for low-contention scenarios

```python
# ❌ BAD: Long transaction with I/O
async with db.transaction():
    user = await users.insert({"name": "Alice"})
    # Don't do this in a transaction!
    await send_email(user['email'])
    await log_to_external_service(user)

# ✅ GOOD: Short transaction, then I/O
async with db.transaction():
    user = await users.insert({"name": "Alice"})

# I/O after transaction
await send_email(user['email'])
await log_to_external_service(user)
```

### Backward Compatibility

Transactions are **completely optional**. Existing code works without changes:

```python
# Without transactions (each operation auto-commits)
user = await users.insert({"name": "Alice"})
await users.update(user)

# With transactions (explicit control)
async with db.transaction():
    user = await users.insert({"name": "Bob"})
    await users.update(user)
```

All CRUD operations automatically participate in active transactions - no code changes needed.

---

## Performance Considerations

### Connection Management

**Always close connections when done:**

```python
# Manual management
db = Database("sqlite+aiosqlite:///myapp.db")
try:
    # Use database
    users = await db.create(User, pk='id')
    # ...
finally:
    await db.close()

# Or use context manager (recommended)
async with Database("sqlite+aiosqlite:///myapp.db") as db:
    users = await db.create(User, pk='id')
    # Connection automatically closed
```

### Bulk Operations

**Use bulk inserts when possible:**

```python
# ❌ Slow: Many individual inserts
for user_data in user_list:
    await users.insert(user_data)

# ✅ Fast: Bulk insert with raw SQL
await db.q("""
    INSERT INTO users (name, email) VALUES
    (?, ?), (?, ?), (?, ?)
""", *flattened_values)
```

### Reflection Costs

**Reflection is expensive - do it once:**

```python
# ❌ Expensive: Reflect on every request
async def get_users():
    await db.reflect()  # Don't do this repeatedly!
    return await db.t.users()

# ✅ Efficient: Reflect once at startup
async def init_app():
    db = Database("sqlite+aiosqlite:///myapp.db")
    await db.reflect()  # Once at startup
    return db

db = await init_app()

async def get_users():
    return await db.t.users()  # Use cached table
```

### Dataclass vs Dict Performance

**Dict operations are slightly faster, but difference is negligible:**

```python
# Dicts: Minimal overhead
users_list = await users()  # Returns List[dict]

# Dataclasses: Small overhead for instantiation
UserDC = users.dataclass()
users_list = await users()  # Returns List[UserDC]
```

**In practice:** Choose based on type safety needs, not performance.

---

## Schema Evolution

### Adding Columns

**Option 1: Raw SQL + Reflection (Recommended)**

```python
# Add column with SQL
await db.q("ALTER TABLE users ADD COLUMN phone TEXT")

# Reflect to pick up changes
await db.reflect_table('users')

# Now usable
user = await db.t.users.insert({"name": "Alice", "phone": "555-1234"})
```

**Option 2: Recreate Table (Development Only)**

```python
# Drop and recreate (loses data!)
await users.drop()

class User:
    id: int
    name: str
    email: str
    phone: str  # New field

users = await db.create(User, pk='id')
```

### Migrations

**Recommended: Use a migration tool alongside DeeBase**

```python
# Use alembic, yoyo, or similar for migrations
# Then reflect the results in DeeBase

async def init_db_after_migrations():
    db = Database("sqlite+aiosqlite:///myapp.db")
    # Migrations already ran, just reflect
    await db.reflect()
    return db
```

---

## CLI vs Python API: Choosing Your Interface

DeeBase provides two complementary interfaces: a command-line interface (CLI) for project setup and schema management, and a Python API for application code. Understanding when to use each is essential for an efficient workflow.

### When to Use the CLI

**Use the CLI for:**

| Task | Why CLI is Better |
|------|-------------------|
| **Project initialization** | `deebase init` creates proper structure, config files |
| **Schema prototyping** | Quickly iterate on table designs without writing code |
| **Database inspection** | Check schemas, list tables/views, see database info |
| **Migration management** | Seal migrations, check status, prepare for deployment |
| **Code generation** | Generate Python models from existing database |
| **Ad-hoc queries** | Quick SQL queries during development |
| **Team onboarding** | New developers can explore schema via CLI |

```bash
# CLI workflow: Set up project and schema
deebase init
deebase table create users id:int name:str email:str:unique --pk id
deebase table create posts id:int author_id:int:fk=users title:str --pk id
deebase index create posts author_id
deebase codegen
deebase migrate seal "initial schema"
```

### When to Use the Python API

**Use the Python API for:**

| Task | Why Python API is Better |
|------|--------------------------|
| **Application code** | Type-safe, async integration with your app |
| **Business logic** | Validation, computed fields, complex operations |
| **Transactions** | Multi-operation atomicity with `db.transaction()` |
| **FK navigation** | `table.fk.column(record)` for relationship traversal |
| **Type safety** | IDE autocomplete, mypy/pyright checking |
| **Testing** | Unit tests, integration tests with fixtures |
| **Bulk operations** | Large inserts, batch updates, streaming |

```python
# Python API: Application code
from deebase import Database

db = Database("sqlite+aiosqlite:///app.db")
await db.reflect()

users = db.t.users
UserDC = users.dataclass()

# Type-safe operations with transactions
async with db.transaction():
    user = await users.insert(UserDC(name="Alice", email="alice@example.com"))
    await posts.insert({"author_id": user.id, "title": "First Post"})
```

### Best Practice: CLI for Setup, Python API for Runtime

The recommended workflow uses both:

1. **CLI during development** - Create/modify schema, generate models
2. **CLI for migrations** - Seal changes, prepare for deployment
3. **Python API in application** - All runtime database operations

```bash
# Development phase (CLI)
deebase init
deebase table create users id:int name:str email:str:unique --pk id
deebase codegen  # Generate models.py
```

```python
# Application code (Python API)
from deebase import Database
from models import Users

db = Database(os.environ["DATABASE_URL"])
await db.reflect()
users = db.t.users
```

### CLI Field Syntax Quick Reference

```bash
# Field format: name:type:modifier1:modifier2...

# Types
id:int              # INTEGER
name:str            # VARCHAR
content:Text        # TEXT (unlimited)
price:float         # REAL/FLOAT
active:bool         # BOOLEAN
data:bytes          # BLOB
metadata:dict       # JSON
created_at:datetime # TIMESTAMP

# Modifiers
email:str:unique           # UNIQUE constraint
bio:Text:nullable          # Allow NULL
status:str:default=active  # DEFAULT 'active'
author_id:int:fk=users     # FOREIGN KEY to users.id

# Combine multiple modifiers
email:str:unique:nullable  # Unique but nullable
```

### Migration Workflow Best Practices

1. **Develop with unsealed migrations** - CLI commands append to current migration
2. **Seal before deployment** - `deebase migrate seal "description"` freezes changes
3. **Never modify sealed migrations** - Create new ones instead
4. **Use descriptive names** - `"add user preferences"` not `"update"`

```bash
# Development: iterate freely
deebase table create preferences id:int user_id:int:fk=users theme:str --pk id
deebase index create preferences user_id

# Ready to deploy: seal it
deebase migrate seal "add user preferences"

# Continue development with new migration
deebase table create notifications id:int user_id:int:fk=users message:Text --pk id
```

### Code Generation Best Practices

1. **Generate after schema changes** - Keep models in sync
2. **Don't manually edit generated files** - Regenerating overwrites changes
3. **Use custom output path** - `--output src/myapp/db/models.py`

```bash
# After schema changes
deebase codegen

# For specific tables only
deebase codegen users posts

# Custom location
deebase codegen --output src/myapp/models/db.py
```

If you need to add custom methods or logic to models, create a separate file that imports from the generated models:

```python
# src/myapp/models/custom.py
from .db import Users, Posts  # Generated models

class UserWithMethods(Users):
    """Extended User with custom methods."""

    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
```

---

## Summary: Quick Decision Guide

| Scenario | Recommendation |
|----------|----------------|
| **Quick script** | Use dicts |
| **Production app** | Use dataclasses |
| **Creating new tables** | Use `db.create()` - no reflection needed |
| **Existing database** | Use `db.reflect()` on startup |
| **Raw SQL table creation** | Follow with `db.reflect_table(name)` |
| **Creating views** | Use `db.create_view()` - no reflection needed |
| **Existing views** | Use `db.reflect_view(name)` |
| **Want type safety** | Call `.dataclass()` immediately after creation/reflection |
| **Need flexibility** | Stick with dicts |
| **Mixed team** | Establish convention early (all dict OR all dataclass per table) |
| **User input** | Catch `ValidationError` and `IntegrityError` |
| **Optional records** | Catch `NotFoundError` |
| **Schema errors** | Usually let fail (programming error) |
| **Multiple tables** | Initialize all at once, configure consistently |
| **Project setup** | Use CLI (`deebase init`) |
| **Schema prototyping** | Use CLI (`deebase table create`) |
| **Application code** | Use Python API |
| **Migration management** | Use CLI (`deebase migrate seal`) |
| **Code generation** | Use CLI (`deebase codegen`) |

---

## Getting Help

Still unsure about a decision?

1. Check the [API Reference](api_reference.md) for detailed method documentation
2. See [Implemented Features](implemented.md) for examples of each feature
3. Review the [examples/](../examples/) folder for runnable code
4. Read [How It Works](how-it-works.md) for technical deep dives

**Rule of Thumb:** When in doubt, start simple (dicts, no dataclass) and add complexity (dataclass, types) when you need it. DeeBase is designed to support both styles seamlessly.
