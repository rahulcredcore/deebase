# Future Phases: FK Navigation & Indexes (Phase 11-12)

This file contains planned features for Phase 11 and 12. These will be implemented after Phase 10 (Enhanced Create).

---

## Phase 11: Foreign Key Relationship Navigation

### Goal
Enable simple navigation from one table to related rows via foreign keys.

### Proposed API

```python
# Get parent record via FK
post = await posts[1]
author = await posts.get_parent(post, "author_id")  # -> User

# Get child records that reference this record
user = await users[1]
user_posts = await users.get_children(user, "posts", "author_id")  # -> [Post, ...]
```

### Key Features
- `table.foreign_keys` property - list FK definitions
- `table.get_parent(record, fk_column)` - fetch referenced parent
- `table.get_children(record, child_table, fk_column)` - fetch referencing children
- Store FK metadata during create/reflect

### What We Won't Implement
- Automatic lazy loading (causes N+1 problems)
- ORM-style relationship() definitions
- Cascade handling (use database constraints)
- Eager loading (use raw SQL)

---

## Phase 12: Indexes and Full-Text Search

### Goal
Support explicit indexes and SQLite FTS5.

### Proposed API

```python
# Create indexes during table creation
articles = await db.create(
    Article,
    pk='id',
    indexes=[
        "slug",                              # Simple index
        ("author_id", "created_at"),         # Composite
        Index("idx_slug", "slug", unique=True),  # Named unique
    ]
)

# Add index after creation
await articles.create_index("title")
await articles.create_index(["author_id", "created_at"], name="idx_author_date")

# Drop index
await articles.drop_index("idx_author_date")

# Full-Text Search (SQLite only)
await articles.enable_fts(["title", "content"])
results = await articles.search("python async tutorial")
await articles.disable_fts()
```

### Key Features
- `indexes` parameter in create()
- `table.create_index(columns, name, unique)`
- `table.drop_index(name)`
- `table.enable_fts(columns)` - SQLite FTS5
- `table.search(query)` - FTS query
- `table.disable_fts()`

### Joins Consideration
Recommend using `db.q()` for joins rather than adding a join API - keeps library simple.

---

## Implementation Order

1. **Phase 10** (current): Enhanced create() with ForeignKey type, defaults, if_not_exists, replace, transform
2. **Phase 11** (future): FK navigation methods
3. **Phase 12** (future): Indexes and FTS

Each phase builds on the previous one.
