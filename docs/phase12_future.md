# Future Phase: Indexes and Full-Text Search (Phase 12)

This file contains planned features for Phase 12. This will be implemented after Phase 11 (FK Navigation).

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

1. **Phase 10** (complete): Enhanced create() with ForeignKey type, defaults, if_not_exists, replace
2. **Phase 11** (current): FK navigation methods
3. **Phase 12** (future): Indexes and FTS

Each phase builds on the previous one.
