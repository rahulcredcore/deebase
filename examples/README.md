# DeeBase Examples

This folder contains runnable examples demonstrating DeeBase features.

## Running Examples

All examples use in-memory SQLite databases and are fully self-contained:

```bash
# Run Phase 1 example (raw SQL)
uv run examples/phase1_raw_sql.py

# Run Phase 2 example (table creation)
uv run examples/phase2_table_creation.py

# Run complete example (combined features)
uv run examples/complete_example.py
```

## Examples

### phase1_raw_sql.py

Demonstrates Phase 1 features:
- Creating database connections
- Executing raw SQL queries
- Creating tables with SQL
- Inserting and querying data
- Handling DDL vs SELECT statements

**Topics covered:**
- `Database()` initialization
- `db.q()` for raw SQL
- DDL statements (CREATE TABLE)
- DML statements (INSERT)
- Query results as dicts
- Database cleanup with `db.close()`

### phase2_table_creation.py

Demonstrates Phase 2 features:
- Creating tables from Python classes
- Rich type support (str, Text, dict/JSON, datetime)
- Optional fields and nullable columns
- Primary key configuration (single and composite)
- Schema inspection
- Table dropping

**Topics covered:**
- `db.create(cls, pk=...)` for table creation
- Type annotations → database columns
- `Text` for unlimited text
- `dict` for JSON columns
- `Optional[T]` for nullable columns
- `table.schema` for SQL inspection
- `table.c` for column access
- `table.drop()` for cleanup

### complete_example.py

A realistic workflow combining Phase 1 & 2:
- Defines a blog database schema
- Creates tables from Python classes
- Populates data with raw SQL
- Queries with JOINs
- Shows schema inspection
- Demonstrates practical usage patterns

**Use case:** Building a simple blog system with authors and posts.

## Key Patterns

### In-Memory Databases

All examples use in-memory databases:
```python
db = Database("sqlite+aiosqlite:///:memory:")
```

This creates a temporary database that exists only during execution.

### Async/Await

All operations are async:
```python
async def main():
    db = Database("...")
    await db.q("SELECT 1")
    await db.close()

asyncio.run(main())
```

### Error-Free Execution

All examples are designed to run without errors and demonstrate best practices for:
- Database initialization
- Schema creation
- Data manipulation
- Resource cleanup

## Next Steps

After running these examples:
1. Read `docs/implemented.md` for complete feature documentation
2. Read `docs/how-it-works.md` for technical internals
3. Check `docs/implementation_plan.md` for upcoming features

## Modifying Examples

Feel free to modify these examples:
- Change the schema definitions
- Try different SQL queries
- Add more tables and relationships
- Experiment with different data types
- Test error conditions

The in-memory database makes experimentation safe and fast!
