# DeeBase Type System Reference

## Overview

DeeBase supports a comprehensive type mapping system that works transparently across SQLite and PostgreSQL.

## Type Mappings

### Basic Types

| Python Type | SQLAlchemy Type | SQLite | PostgreSQL |
|-------------|-----------------|---------|------------|
| `int` | `Integer` | INTEGER | INTEGER |
| `str` | `String` | TEXT | VARCHAR |
| `float` | `Float` | REAL | DOUBLE PRECISION |
| `bool` | `Boolean` | INTEGER (0/1) | BOOLEAN |
| `bytes` | `LargeBinary` | BLOB | BYTEA |
| `datetime` | `DateTime` | TEXT (ISO8601) | TIMESTAMP |
| `date` | `Date` | TEXT (ISO8601) | DATE |
| `time` | `Time` | TEXT (ISO8601) | TIME |

### Special Types

#### Text (Unlimited Text)

For long-form text content (essays, articles, documents), use the `Text` marker:

```python
from deebase import Text

class Article:
    id: int
    title: str          # VARCHAR (limited string)
    author: str         # VARCHAR (limited string)
    content: Text       # TEXT (unlimited)
    summary: Text       # TEXT (unlimited)
```

**Database mapping:**
- **SQLite**: `TEXT` (unlimited)
- **PostgreSQL**: `TEXT` (unlimited)

#### JSON (Structured Data)

For storing structured data as JSON, use Python's `dict` type:

```python
class User:
    id: int
    name: str
    settings: dict      # JSON column
    metadata: dict      # JSON column
```

**Database mapping:**
- **PostgreSQL**: `JSON` column (native JSON support)
- **SQLite**: `TEXT` column with automatic JSON serialization/deserialization

**SQLAlchemy handles serialization automatically**, so you can work with Python dicts seamlessly:

```python
user = await users.insert({
    "name": "Alice",
    "settings": {"theme": "dark", "notifications": True},
    "metadata": {"created_by": "admin", "tags": ["vip", "beta"]}
})

# settings and metadata are automatically serialized to JSON
# When retrieved, they're automatically deserialized to Python dicts
```

### Nullable Types

Use `Optional[T]` for nullable columns:

```python
from typing import Optional

class User:
    id: int
    name: str
    email: Optional[str]         # Nullable VARCHAR
    bio: Optional[Text]          # Nullable TEXT
    preferences: Optional[dict]  # Nullable JSON
```

### ForeignKey (Relationships)

Use `ForeignKey[T, "table"]` to define foreign key relationships:

```python
from deebase import ForeignKey

class Post:
    id: int
    title: str
    author_id: ForeignKey[int, "user"]       # FK to user.id (default column)
    category_id: ForeignKey[int, "category"] # FK to category.id

class Comment:
    id: int
    post_id: ForeignKey[int, "post"]         # FK to post.id
    content: str
```

**Syntax options:**
- `ForeignKey[int, "user"]` - References `user.id` (default column is `id`)
- `ForeignKey[str, "user.uuid"]` - References `user.uuid` explicitly

**Database mapping:**
- Creates a `FOREIGN KEY` constraint in the table definition
- The first type parameter (`int`, `str`) determines the column type
- FK constraints are enforced at the database level

**SQLite note:** Enable FK enforcement with:
```python
await db.q("PRAGMA foreign_keys = ON")
```

**Example with constraint violation:**
```python
from deebase import IntegrityError

try:
    await posts.insert({
        "title": "Test",
        "author_id": 999  # Non-existent user!
    })
except IntegrityError as e:
    print(f"FK violation: {e.constraint}")
```

### Index (Query Optimization)

Use `Index` to create named indexes for query optimization:

```python
from deebase import Index

# Named unique index
idx = Index("idx_email", "email", unique=True)

# Named composite index
idx = Index("idx_author_date", "author_id", "created_at")

# Use in db.create()
articles = await db.create(
    Article,
    pk='id',
    indexes=[
        "slug",                                    # Auto-named: ix_article_slug
        ("author_id", "created_at"),               # Auto-named composite
        Index("idx_title", "title", unique=True),  # Named unique index
    ]
)
```

**Constructor:**
- `Index(name: str, *columns: str, unique: bool = False)`

**Index specification options in `db.create()`:**
- `"column"` - Single column index with auto-generated name (`ix_tablename_column`)
- `("col1", "col2")` - Composite index with auto-generated name
- `Index("name", "col")` - Named index
- `Index("name", "col", unique=True)` - Named unique index
- `Index("name", "col1", "col2")` - Named composite index

**Database mapping:**
- Creates a `CREATE INDEX` statement after table creation
- Unique indexes create `UNIQUE INDEX` constraints
- Works identically on SQLite and PostgreSQL

**Managing indexes after table creation:**
```python
# Add index
await table.create_index("column")
await table.create_index(["col1", "col2"], name="idx_custom")
await table.create_index("email", unique=True)

# List indexes
for idx in table.indexes:
    print(f"{idx['name']}: {idx['columns']} (unique={idx['unique']})")

# Drop index
await table.drop_index("idx_custom")
```

**Important notes:**
- Index is NOT a column type - it's used in the `indexes` parameter of `db.create()`
- Indexes improve read performance but slow down writes
- Unique indexes enforce uniqueness constraints (raise `IntegrityError` on duplicates)

### Default Values

Use Python class defaults for SQL `DEFAULT` values:

```python
class Article:
    id: int
    title: str
    status: str = "draft"      # SQL DEFAULT 'draft'
    views: int = 0             # SQL DEFAULT 0
    featured: bool = False     # SQL DEFAULT 0 (SQLite)
```

**Supported default types:**
- `str` - String defaults (quoted in SQL)
- `int` - Integer defaults
- `float` - Float defaults
- `bool` - Boolean defaults (0/1 in SQLite)

**Important notes:**
- Only scalar types are extracted for SQL defaults
- Mutable defaults (`dict`, `list`) are NOT used for SQL defaults
- `default_factory` is NOT used for SQL defaults (runtime-only)
- Defaults work with both regular classes and `@dataclass`

**Example:**
```python
# Insert without specifying defaults
article = await articles.insert({"title": "Hello"})
print(article["status"])   # "draft" (from SQL default)
print(article["views"])    # 0 (from SQL default)
print(article["featured"]) # False (from SQL default)
```

## Usage Examples

### Simple Table with Mixed Types

```python
from typing import Optional
from datetime import datetime
from deebase import Database, Text

class BlogPost:
    id: int
    title: str                      # VARCHAR
    slug: str                       # VARCHAR
    content: Text                   # TEXT (unlimited)
    excerpt: Optional[str]          # VARCHAR (nullable)
    metadata: dict                  # JSON
    published_at: Optional[datetime]  # TIMESTAMP (nullable)
    view_count: int                 # INTEGER

db = Database("sqlite+aiosqlite:///blog.db")
posts = await db.create(BlogPost, pk='id')

# Insert with mixed types
post = await posts.insert({
    "title": "Getting Started with DeeBase",
    "slug": "getting-started",
    "content": "This is a very long article content...",  # No length limits
    "excerpt": "Quick intro to DeeBase",
    "metadata": {
        "author": "Alice",
        "tags": ["tutorial", "python"],
        "featured": True
    },
    "view_count": 0
})

# Retrieve - JSON automatically deserialized
post = await posts[1]
print(post["metadata"]["tags"])  # ["tutorial", "python"]
```

### JSON Column Benefits

1. **Query JSON fields** (PostgreSQL has rich JSON operators, SQLite has JSON functions):
   ```python
   # Raw SQL with JSON access (PostgreSQL)
   await db.q("SELECT * FROM posts WHERE metadata->>'featured' = 'true'")

   # Raw SQL with JSON access (SQLite)
   await db.q("SELECT * FROM posts WHERE json_extract(metadata, '$.featured') = 1")
   ```

2. **Automatic serialization/deserialization**:
   ```python
   # Python dict → JSON string (automatic)
   await posts.insert({"metadata": {"key": "value"}})

   # JSON string → Python dict (automatic)
   post = await posts[1]
   assert isinstance(post["metadata"], dict)
   ```

3. **Nested structures**:
   ```python
   metadata = {
       "author": {
           "name": "Alice",
           "email": "alice@example.com"
       },
       "tags": ["python", "async"],
       "stats": {
           "views": 100,
           "likes": 25
       }
   }
   ```

## Type System Design

### Why str vs Text?

- **`str` (VARCHAR)**: For short strings with potential length constraints
  - Names, emails, usernames, slugs
  - Can add length limits later if needed
  - More portable across databases

- **`Text` (TEXT)**: For unlimited text content
  - Articles, blog posts, essays, comments
  - No length restrictions
  - Explicitly signals "this is long-form content"

### Why dict for JSON?

- Natural Python type for structured data
- SQLAlchemy handles cross-database differences automatically
- Works seamlessly in both SQLite and PostgreSQL
- No need to manually serialize/deserialize

## Future Enhancements

Planned features:
- Length constraints: `Annotated[str, "varchar(255)"]`
- Custom types: UUID, Decimal, etc.
- Array types (PostgreSQL)
- JSONB preference (PostgreSQL for better performance)
