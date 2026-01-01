# Future Phase: Indexes (Phase 12)

This file contains planned features for Phase 12. This will be implemented after Phase 11 (FK Navigation) is complete.

---

## Phase 12: Indexes

### Goal
Support explicit indexes for query optimization.

### Scope Changes
- **FTS removed:** Full-Text Search (FTS5) was removed from scope as it's SQLite-only. Adding PostgreSQL support would require different implementation (tsvector/tsquery).
- **Joins solved:** JOIN queries are elegantly handled via views - see [best-practices.md](best-practices.md#using-views-for-joins-and-ctes)

### Proposed API

```python
from deebase import Index

# Create indexes during table creation
articles = await db.create(
    Article,
    pk='id',
    indexes=[
        "slug",                                    # Simple index
        ("author_id", "created_at"),               # Composite index
        Index("idx_slug", "slug", unique=True),    # Named unique index
    ]
)

# Add index after creation
await articles.create_index("title")
await articles.create_index(["author_id", "created_at"], name="idx_author_date")
await articles.create_index("email", unique=True)

# Drop index
await articles.drop_index("idx_author_date")

# List indexes on a table
print(articles.indexes)
# [{'name': 'idx_slug', 'columns': ['slug'], 'unique': True}, ...]
```

### Key Features
- `Index` class exported from deebase
- `indexes` parameter in `db.create()`
- `table.create_index(columns, name=None, unique=False)`
- `table.drop_index(name)`
- `table.indexes` property

### Implementation Details

1. **`Index` class for named indexes**
   - `Index(name, *columns, unique=False)`
   - Used in `indexes` parameter for `db.create()`
   - Mirrors SQLAlchemy's Index class

2. **`indexes` parameter in `db.create()`**
   - Accept list of column names, tuples, or Index objects
   - String: `"column"` → simple index with auto-generated name
   - Tuple: `("col1", "col2")` → composite index with auto-generated name
   - Index: `Index("name", "col", unique=True)` → named index with options
   - Auto-generate names like `ix_tablename_column`

3. **`table.create_index(columns, name=None, unique=False)`**
   - Create index on existing table
   - Accept string (single column) or list (composite)
   - Auto-generate name if not provided
   - Uses SQLAlchemy DDL

4. **`table.drop_index(name)`**
   - Drop index by name
   - Uses `DROP INDEX` DDL

5. **`table.indexes` property**
   - Return list of index definitions
   - Format: `[{'name': str, 'columns': [str], 'unique': bool}, ...]`
   - Populated from SQLAlchemy metadata inspection

### Tests (~20-25 new tests)
- Create table with simple index
- Create table with composite index
- Create table with named unique index
- `create_index()` on existing table
- `create_index()` with auto-generated name
- `drop_index()` removes index
- `indexes` property lists indexes
- Index auto-naming convention
- Invalid column name raises ValidationError
- Duplicate index name handling

### Deliverables
- `Index` class exported from deebase
- `indexes` parameter on `db.create()`
- `table.create_index()` method
- `table.drop_index()` method
- `table.indexes` property
- ~20-25 new tests
- Phase 12 example file
- Documentation updates

---

## Implementation Order

1. **Phase 10** (complete): Enhanced create() with ForeignKey type, defaults, if_not_exists, replace
2. **Phase 11** (complete): FK navigation methods
3. **Phase 12** (next): Indexes

Each phase builds on the previous one.
