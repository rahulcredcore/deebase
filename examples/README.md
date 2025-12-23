# DeeBase Examples

This folder contains runnable examples demonstrating DeeBase features.

## Running Examples

All examples use in-memory SQLite databases and are fully self-contained:

```bash
# Run Phase 1 example (raw SQL)
uv run examples/phase1_raw_sql.py

# Run Phase 2 example (table creation)
uv run examples/phase2_table_creation.py

# Run Phase 3 example (CRUD operations)
uv run examples/phase3_crud_operations.py

# Run Phase 4 example (dataclass support)
uv run examples/phase4_dataclass_support.py

# Run Phase 5 example (reflection and dynamic access)
uv run examples/phase5_reflection.py

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

### phase3_crud_operations.py

Demonstrates Phase 3 CRUD features:
- Insert records with auto-generated PKs
- Select all/limited records
- Get records by primary key
- Lookup records by column values
- Update existing records
- Delete records
- Upsert (insert or update)
- Composite primary keys
- Rich types (Text, JSON, datetime)
- with_pk parameter
- Error handling with NotFoundError
- xtra() filtering

**Topics covered:**
- `table.insert(record)` - Create records
- `table()` and `table(limit=N)` - Read all/limited
- `table[pk]` - Read by primary key
- `table.lookup(**kwargs)` - Find by conditions
- `table.update(record)` - Update records
- `table.delete(pk)` - Delete records
- `table.upsert(record)` - Insert or update
- `table(with_pk=True)` - Return (pk, record) tuples
- `table.xtra(**filters)` - Apply filters
- Composite primary keys with tuples
- Rich type handling (Text, dict/JSON, datetime)

### phase4_dataclass_support.py

Demonstrates Phase 4 dataclass features:
- Generating dataclasses from table metadata
- CRUD operations with dataclass instances
- Using actual @dataclass decorated classes
- Mixing dict and dataclass inputs
- Type-safe database operations
- Rich types with dataclasses

**Topics covered:**
- `table.dataclass()` - Generate dataclass from table
- Insert/update with dataclass instances
- Using `@dataclass` decorator with `db.create()`
- Type safety and IDE autocomplete
- Dataclass field access (`.name`, `.email`, etc.)
- Before/after `.dataclass()` behavior
- Mixing dict and dataclass in operations

### phase5_reflection.py

Demonstrates Phase 5 reflection and dynamic access features:
- Reflecting existing tables with `db.reflect()`
- Single table reflection with `db.reflect_table()`
- Dynamic table access via `db.t.tablename`
- Multiple table access via `db.t['table1', 'table2']`
- Working with existing databases
- Mixed workflows (db.create() + raw SQL + reflection)
- CRUD operations on reflected tables

**Topics covered:**
- `db.reflect()` - Reflect all tables from database
- `db.reflect_table(name)` - Reflect single table
- `db.t.tablename` - Sync cache access
- `db.t['table']` - Index access
- `db.t['table1', 'table2']` - Multiple tables
- Schema preservation and inspection
- Error messages for non-reflected tables
- Combining db.create() and reflection

### complete_example.py

A realistic workflow combining all phases (1-5):
- Defines a blog database schema
- Creates tables from Python classes
- Populates data with CRUD operations
- Queries with raw SQL and JOINs
- Demonstrates CRUD operations
- Enables dataclass mode for type-safe operations
- Shows schema inspection
- Demonstrates practical usage patterns

**Use case:** Building a complete blog system with authors and posts.

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
