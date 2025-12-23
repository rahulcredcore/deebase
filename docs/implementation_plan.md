# DeeBase Implementation Plan

Async SQLAlchemy-based implementation of the fastlite API for SQLite and PostgreSQL.

## Project Overview

DeeBase is an async database library that replicates the fastlite API using SQLAlchemy as the backend. It provides:
- Ergonomic, interactive database access
- Async/await support for FastAPI and modern async Python
- SQLite and PostgreSQL backends
- Opt-in type safety with dataclasses
- Simple CRUD operations with minimal boilerplate

## Project Structure

```
deebase/
├── src/
│   └── deebase/
│       ├── __init__.py           # Public API exports
│       ├── database.py           # Database class
│       ├── table.py              # Table class
│       ├── column.py             # Column class
│       ├── view.py               # View class
│       ├── types.py              # Type mapping (Python -> SQLAlchemy)
│       ├── dataclass_utils.py    # Dataclass generation and handling
│       └── exceptions.py         # NotFoundError, etc.
├── tests/
│   ├── conftest.py               # Test fixtures
│   ├── test_database.py
│   ├── test_table.py
│   └── test_crud.py
└── docs/
    └── implementation_plan.md    # This file
```

## Core Technical Decisions

### 1. Async Session Management
- Use `AsyncEngine` from `sqlalchemy.ext.asyncio`
- Each `Database` instance owns an engine
- Operations create short-lived `AsyncSession` contexts internally
- Pattern: `async with self._session() as session:` for each operation

### 2. Table Metadata Management
- Keep `sqlalchemy.Table` objects in a registry/cache
- Use SQLAlchemy reflection to discover existing tables
- Build `Table` metadata when creating new tables from classes
- Each `Table` class wraps a `sqlalchemy.Table` instance

### 3. Dataclass Association
- Store optional dataclass reference on `Table` instances
- When dataclass exists, use it for serialization/deserialization
- Without dataclass, return dicts from SQLAlchemy `Row` objects
- Generate dataclasses dynamically using Python's `dataclasses.make_dataclass()`

### 4. Dynamic Table/Column Access
- `db.t` returns a `TableAccessor` proxy object
- Override `__getattr__` and `__getitem__` to fetch/create `Table` instances
- Lazy-load table metadata on first access
- Similar pattern for `db.v` (ViewAccessor)

### 5. Database-Agnostic Design
- **Connection string only difference**: `sqlite+aiosqlite:///file.db` vs `postgresql+asyncpg://...`
- All operations use SQLAlchemy Core APIs
- No raw SQL except in `q()` method
- Type mapping might need dialect-specific tweaks (later phase)

### 6. SQLAlchemy Exposure Strategy
Allow "escape hatches" to underlying SQLAlchemy:
```python
# Access wrapped objects
table.sa_table  # The sqlalchemy.Table object
column.sa_column  # The sqlalchemy.Column object
db.engine  # The AsyncEngine

# Dispatch unknown attributes
table.some_sqlalchemy_method()  # Falls through to sa_table via __getattr__
```

### 7. Text and JSON Type Support
Support for both limited and unlimited text, plus structured JSON data:

**Text Type Strategy:**
- `str` → `sa.String` → VARCHAR (for short strings: names, emails, slugs)
- `Text` marker class → `sa.Text` → TEXT (for unlimited text: essays, articles)
- Import via: `from deebase import Text`

**JSON Type Support:**
- `dict` → `sa.JSON` → JSON in PostgreSQL, TEXT in SQLite (auto-serialized)
- Automatic serialization/deserialization of Python dicts
- Transparent cross-database support

**Example:**
```python
from deebase import Text

class Article:
    title: str          # VARCHAR (short string)
    author: str         # VARCHAR (short string)
    content: Text       # TEXT (unlimited)
    metadata: dict      # JSON column (auto-serialized)
```

## Key Classes and Responsibilities

### Database Class

```python
Database:
  - __init__(url: str)
  - Properties:
    - t: TableAccessor (dynamic table access)
    - v: ViewAccessor (dynamic view access)
    - engine: AsyncEngine (expose underlying SQLAlchemy)
  - Methods:
    - async q(query: str) -> list[dict]
    - async create(cls, pk=None) -> Table
    - async create_view(name, sql, replace=False)
    - async import_file(...) (phase 2)
    - _get_table(name) -> Table (internal cache lookup)
    - _session() -> AsyncContextManager[AsyncSession]
```

**Implementation notes:**
- Constructor creates `AsyncEngine` from URL
- Keep a `_tables: dict[str, Table]` cache
- `q()` executes raw SQL, returns list of `row._mapping` dicts
- `create()` inspects class annotations, builds SQLAlchemy Table, executes DDL

### Table Class

```python
Table:
  - __init__(name, sa_table: sqlalchemy.Table, engine, dataclass_cls=None)
  - Properties:
    - c: ColumnAccessor
    - schema: str (get DDL)
    - sa_table: sqlalchemy.Table (expose SQLAlchemy)
  - Methods:
    - async insert(record: dict | dataclass) -> dict | dataclass
    - async update(record: dict | dataclass) -> dict | dataclass
    - async upsert(record: dict | dataclass) -> dict | dataclass
    - async delete(pk_value)
    - async lookup(**kwargs) -> dict | dataclass
    - dataclass() -> type (generate/return dataclass)
    - xtra(**kwargs) -> Table (return filtered copy)
    - async __call__(limit=None, with_pk=False) -> list
    - async __getitem__(pk) -> dict | dataclass
    - async drop()
    - async transform(**kwargs) (phase 2)
  - Internal:
    - _xtra_filters: dict (for xtra() filtering)
    - _to_dict(row: Row) -> dict
    - _to_dataclass(row: Row) -> dataclass
    - _from_input(record) -> dict (convert input to dict)
    - _apply_xtra(stmt) -> statement (apply filters)
```

**Implementation notes:**
- Wraps a `sqlalchemy.Table` object
- CRUD operations use SQLAlchemy Core (select/insert/update/delete)
- `_dataclass_cls` determines return type behavior
- `xtra()` returns new `Table` instance with `_xtra_filters` set
- All queries apply `_xtra_filters` automatically
- Primary key extraction from `sa_table.primary_key`

### TableAccessor Class

```python
TableAccessor:
  - __init__(db: Database)
  - __getattr__(name) -> Table (db.t.users)
  - __getitem__(name_or_names) -> Table | tuple[Table] (db.t['users'] or db.t['users', 'posts'])
  - async _load_table(name) -> Table (reflect from DB)
```

**Implementation notes:**
- Proxy for dynamic table access
- Use SQLAlchemy reflection to load existing tables
- Cache in `Database._tables`

### ColumnAccessor Class

```python
ColumnAccessor:
  - __init__(sa_table: sqlalchemy.Table)
  - __getattr__(name) -> Column
  - __iter__() -> Iterator[Column]
```

### Column Class

```python
Column:
  - __init__(sa_column: sqlalchemy.Column)
  - __str__() -> str (SQL-safe column name)
  - __repr__() -> str
  - sa_column: sqlalchemy.Column (expose SQLAlchemy)
```

**Implementation notes:**
- Wraps `sqlalchemy.Column`
- `__str__()` returns quoted identifier for SQL safety
- Attribute access can dispatch to `sa_column` via `__getattr__`

### View Class

```python
View:
  - Similar to Table but read-only
  - No insert/update/delete/upsert methods
  - Only query operations: __call__, __getitem__, lookup
```

## Type Mapping (types.py)

```python
Python type → SQLAlchemy type → Database columns:
- int → Integer → INTEGER
- str → String → VARCHAR (SQLite: TEXT, PostgreSQL: VARCHAR)
- Text → Text → TEXT (unlimited text in both databases)
- float → Float → REAL/FLOAT
- bool → Boolean → BOOLEAN (SQLite: INTEGER 0/1)
- bytes → LargeBinary → BLOB/BYTEA
- dict → JSON → JSON (PostgreSQL: JSON, SQLite: TEXT with auto-serialization)
- datetime.datetime → DateTime → TIMESTAMP/DATETIME
- datetime.date → Date → DATE
- datetime.time → Time → TIME
- Optional[T] → nullable=True (allows NULL values)
```

**Special Types:**
- `Text`: Marker class for unlimited text columns (essays, articles)
  - Usage: `from deebase import Text`
  - Maps to `sa.Text()` → TEXT column in both databases
- `dict`: Native Python dict for JSON data
  - Maps to `sa.JSON()` → JSON in PostgreSQL, TEXT in SQLite
  - Automatic serialization/deserialization

## Dataclass Utilities (dataclass_utils.py)

```python
Functions:
- extract_annotations(cls) -> dict[str, type]
  Extract type hints from class

- make_table_dataclass(table_name: str, sa_table: sqlalchemy.Table) -> type
  Generate dataclass from SQLAlchemy Table metadata
  All fields Optional for auto-generated values

- record_to_dict(record: Any) -> dict
  Convert dict/dataclass/object to dict

- dict_to_dataclass(data: dict, cls: type) -> dataclass
  Instantiate dataclass from dict
```

## Exception Classes

```python
class NotFoundError(Exception):
    """Raised when query returns no results"""
    pass
```

## Implementation Phases

### Phase 1: Core Infrastructure ✅ COMPLETE

**Status:** All items completed + enhancements

1. **✅ Setup project structure**
   - Created package structure in src/deebase
   - Setup dependencies: `sqlalchemy[asyncio]`, `aiosqlite`, `greenlet`, `pytest-asyncio`
   - Created test infrastructure with pytest-asyncio

2. **✅ Database class basics**
   - Constructor with AsyncEngine creation
   - `async q()` method for raw SQL (handles both SELECT and DDL/DML)
   - Session management helper `_session()` with auto-commit/rollback
   - Context manager support (`async with Database(...)`)
   - Fixed: Check `result.returns_rows` before calling `fetchall()`

3. **✅ Type mapping system (ENHANCED)**
   - Python type → SQLAlchemy type converter
   - Handle Optional types for nullable columns
   - **Added:** `Text` marker class for unlimited TEXT columns
   - **Added:** `dict` type for JSON columns (cross-database support)
   - Support for: int, str, Text, float, bool, bytes, dict, datetime, date, time
   - Complete Optional[T] support

4. **✅ Test infrastructure**
   - Async test fixtures with in-memory SQLite
   - Sample data fixtures
   - Helper fixtures for test data
   - **62 tests passing** (100% pass rate)

5. **✅ Supporting classes (COMPLETE)**
   - Column and ColumnAccessor with SQL-safe stringification
   - Table class structure with method stubs
   - View class for read-only views
   - NotFoundError exception

6. **✅ Dataclass utilities (COMPLETE)**
   - extract_annotations() - Extract type hints from classes
   - make_table_dataclass() - Generate dataclasses from SQLAlchemy tables
   - sqlalchemy_type_to_python() - Reverse type mapping
   - record_to_dict() - Convert any record format to dict
   - dict_to_dataclass() - Instantiate dataclasses from dicts

**Deliverables:**
- Fully functional Database class with `q()` method
- Complete type system with Text and JSON support
- All utility functions tested and working
- 62 passing tests covering all Phase 1 functionality
- Documentation: types_reference.md

**Key Decisions Made:**
- Chose marker class approach for `Text` type (Option 1)
- Added `dict` → JSON mapping for structured data
- Fixed `q()` to handle both queries and DDL/DML statements

### Phase 2: Table Creation & Schema ✅ COMPLETE

**Status:** All items completed

1. **✅ db.create() implementation**
   - Parse class annotations
   - Map to SQLAlchemy types (using enhanced type system with Text and JSON)
   - Handle primary key specification (single & composite)
   - Execute CREATE TABLE via SQLAlchemy
   - Return Table instance with dataclass support
   - Cache created tables

2. **✅ Table class enhancements**
   - Constructor (already existed)
   - Store sa_table reference (done)
   - Expose `schema` property (compile CREATE TABLE SQL)
   - Implement `drop()` method to drop tables

3. **✅ Tests**
   - Create tables from simple classes
   - Verify schema generation with Text and JSON types
   - Test primary key specification (single & composite)
   - Test Optional fields become nullable columns
   - Test table drop functionality
   - **16 new tests, all passing**

**Deliverables:**
- Fully functional table creation from Python classes
- Rich type support (str, Text, dict/JSON, datetime, Optional)
- Schema generation and inspection
- Table dropping
- 78 total passing tests (62 + 16 new)
- Documentation: implemented.md with usage examples

**What Works Now:**
```python
class Article:
    id: int
    title: str
    content: Text
    metadata: dict
    created_at: datetime

articles = await db.create(Article, pk='id')
print(articles.schema)  # View CREATE TABLE SQL
await articles.drop()   # Drop table
```

### Phase 3: CRUD Operations ✅ COMPLETE

**Status:** All items completed

1. **✅ Table.insert() returning dicts**
   - Accept dict input
   - Execute SQLAlchemy insert
   - Return inserted row as dict with auto-generated PKs
   - Handle composite primary keys
   - Apply xtra filters automatically

2. **✅ Table.update()**
   - Update by PK in record
   - Return updated record dict
   - Raise NotFoundError if record not found
   - Respect xtra filters

3. **✅ Table.upsert()**
   - Check if record exists by PK with SELECT
   - Insert or update accordingly
   - Database-agnostic implementation (SELECT → INSERT/UPDATE)
   - Return upserted record dict
   - Handles missing PKs (inserts)

4. **✅ Table.delete()**
   - Delete by PK value (single or composite)
   - Raise NotFoundError if record not found
   - Respect xtra filters

5. **✅ Table.__call__() and Table[pk]**
   - Implement select all/with limit
   - Implement get by primary key (single and composite)
   - Return dicts (or dataclasses when _dataclass_cls is set)
   - Raise NotFoundError for missing records
   - with_pk parameter returns (pk_value, record) tuples

6. **✅ Table.lookup()**
   - Query with WHERE conditions
   - Return single record dict
   - Raise NotFoundError if not found
   - Support multiple filter conditions

7. **✅ Tests**
   - Full CRUD cycle with dicts (including upsert)
   - Error cases (NotFoundError)
   - Composite primary keys
   - Upsert insert vs update behavior
   - Rich types (Text, JSON, datetime, Optional)
   - xtra() filtering on all operations
   - with_pk parameter
   - **27 new tests, all passing**

**Deliverables:**
- Complete CRUD operations (insert, update, upsert, delete, select, lookup)
- Composite primary key support throughout
- Auto-generated PK handling
- xtra() filtering applies to all operations
- Comprehensive error handling with NotFoundError
- with_pk parameter for accessing primary key values
- 105 total passing tests (78 + 27 new)
- Documentation: Full Phase 3 section in implemented.md and how-it-works.md
- Examples: phase3_crud_operations.py and updated complete_example.py

**What Works Now:**
```python
class User:
    id: int
    name: str
    email: str

users = await db.create(User, pk='id')

# INSERT
user = await users.insert({"name": "Alice", "email": "alice@example.com"})
# Returns: {'id': 1, 'name': 'Alice', 'email': 'alice@example.com'}

# SELECT
all_users = await users()
limited = await users(limit=10)
with_pks = await users(with_pk=True)  # [(1, {...}), (2, {...}), ...]

# GET by PK
user = await users[1]

# LOOKUP
user = await users.lookup(email="alice@example.com")

# UPDATE
user['name'] = "Alice Smith"
updated = await users.update(user)

# UPSERT
await users.upsert({"id": 1, "name": "Updated", "email": "new@example.com"})

# DELETE
await users.delete(1)

# xtra() filtering
admin_users = users.xtra(role="admin")
admins = await admin_users()  # Only admin users
```

**Key Implementation Details:**
- Built on SQLAlchemy Core DML (sa.insert, sa.update, sa.delete, sa.select)
- Session-per-operation pattern with auto-commit/rollback
- Insert + SELECT pattern to fetch complete records with auto-generated values
- Database-agnostic upsert (SELECT → INSERT/UPDATE)
- Composite PK support via tuple handling
- Record conversion via _to_record() and _from_input() helpers

### Phase 4: Dataclass Support ✅ COMPLETE

**Status:** All items completed

1. **✅ Dataclass generation**
   - `Table.dataclass()` implementation
   - Generate from SQLAlchemy table metadata with `make_table_dataclass()`
   - Make fields Optional for auto-increment PKs
   - Cache on Table instance
   - Handle both plain classes and actual `@dataclass`

2. **✅ CRUD operations use dataclasses**
   - `_to_record()` checks `_dataclass_cls` and `is_dataclass()`
   - Accept dataclass instances as input via `_from_input()`
   - Return dataclass instances when configured
   - Maintain full dict support (seamless mixing)

3. **✅ Tests**
   - Generate dataclass with `.dataclass()` → 3 tests
   - CRUD operations return dataclass instances → 6 tests
   - Create with actual `@dataclass` → 2 tests
   - Mix dict and dataclass inputs → 3 tests
   - Rich types with dataclasses → 3 tests
   - Before/after `.dataclass()` behavior → 3 tests
   - **20 new tests, all passing**

**Deliverables:**
- Fully functional `.dataclass()` method
- All CRUD operations support dataclass instances (input and output)
- Support for actual `@dataclass` decorated classes
- Seamless mixing of dicts and dataclasses
- Type-safe operations with IDE autocomplete
- 125 total passing tests (105 + 20 new)
- Documentation: Full Phase 4 section in implemented.md and how-it-works.md
- Examples: phase4_dataclass_support.py and updated complete_example.py

**What Works Now:**
```python
class User:
    id: int
    name: str
    email: str

users = await db.create(User, pk='id')

# Before .dataclass() - returns dicts
user1 = await users.insert({"name": "Alice", "email": "alice@example.com"})
print(type(user1))  # <class 'dict'>

# Generate dataclass
UserDC = users.dataclass()

# After .dataclass() - returns dataclass instances
user2 = await users.insert({"name": "Bob", "email": "bob@example.com"})
print(type(user2))  # <class 'deebase.dataclass_utils.User'>
print(user2.name)   # 'Bob' - field access!

# Insert with dataclass instance
user3 = await users.insert(UserDC(id=None, name="Charlie", email="charlie@example.com"))

# All CRUD operations work with dataclasses
all_users = await users()  # Returns list of UserDC instances
for user in all_users:
    print(user.name)  # Type-safe field access

# Or use actual @dataclass
from dataclasses import dataclass
from typing import Optional

@dataclass
class Product:
    id: Optional[int] = None
    name: str = ""
    price: float = 0.0

products = await db.create(Product, pk='id')
# Automatically uses Product dataclass - no need to call .dataclass()

widget = await products.insert(Product(name="Widget", price=9.99))
print(isinstance(widget, Product))  # True
```

**Key Implementation Details:**
- `.dataclass()` checks `is_dataclass()` before generating
- `_to_record()` only converts to dataclass if `_dataclass_cls` is actual dataclass
- `_from_input()` accepts any input (dict, dataclass, object) via `record_to_dict()`
- Generated dataclasses have Optional fields (default None) for auto-increment
- Seamless mixing of dicts and dataclasses in all operations

### Phase 5: Dynamic Access & Reflection ✅ COMPLETE

**Status:** All items completed (with design modification)

**Note:** ColumnAccessor was already implemented in Phase 1

**Design Decision:** Changed from lazy loading to explicit reflection due to async/sync mismatch. `__getattr__` is synchronous but SQLAlchemy reflection with `AsyncEngine` requires async operations.

1. **✅ Database.reflect() - Explicit reflection of all tables**
   - Async method that reflects all tables from database
   - Uses SQLAlchemy's `metadata.reflect()` with `AsyncEngine`
   - Wraps each reflected table in our Table class
   - Caches all tables in `_db._tables`
   - Skips already-cached tables (from `db.create()`)

2. **✅ Database.reflect_table(name) - Single table reflection**
   - Async method that reflects a specific table
   - Returns cached table if already exists
   - Uses SQLAlchemy's `Table(..., autoload_with=conn)`
   - Wraps and caches the reflected table
   - Makes table available via `db.t.tablename`

3. **✅ TableAccessor implementation - Cache-only access**
   - `__getattr__` for attribute access (e.g., `db.t.users`)
   - `__getitem__` for index access (e.g., `db.t['users']`)
   - Multiple table access (e.g., `db.t['users', 'posts']`)
   - Synchronous cache-only access (no lazy loading)
   - Raises helpful AttributeError if table not in cache

4. **✅ Tests**
   - Reflect tables created with raw SQL → 4 tests
   - Access via db.t.table_name → 4 tests
   - Access via db.t['table_name'] and multiple → 2 tests
   - Reflect single table with reflect_table() → 3 tests
   - Complete workflows (reflect + CRUD) → 3 tests
   - **16 new tests, all passing**

**Deliverables:**
- `db.reflect()` method for reflecting all tables
- `db.reflect_table(name)` for single table reflection
- Cache-only TableAccessor with helpful error messages
- Support for tables created with raw SQL
- Seamless integration with `db.create()` (auto-cached)
- 142 total passing tests (126 + 16 new)

**What Works Now:**
```python
db = Database("sqlite+aiosqlite:///myapp.db")

# Tables created via db.create() are auto-cached
users = await db.create(User, pk='id')
users = db.t.user  # ✅ Works immediately (cache hit)

# Tables created with raw SQL need explicit reflection
await db.q("CREATE TABLE products (id INT PRIMARY KEY, name TEXT)")
await db.reflect_table('products')  # Reflect this table
products = db.t.products  # ✅ Now works (cache hit)

# Or reflect all tables at once
await db.q("CREATE TABLE orders (...)")
await db.q("CREATE TABLE customers (...)")
await db.reflect()  # Reflect everything
orders = db.t.orders        # ✅ Works
customers = db.t.customers  # ✅ Works

# Multiple table access
users, products = db.t['user', 'products']  # ✅ Works

# CRUD operations work on reflected tables
customer = await customers.insert({"name": "Alice"})
all_customers = await customers()
```

**Key Design Change:**
- **Original plan:** Lazy loading (automatic reflection in `__getattr__`)
- **Implemented:** Explicit reflection (`await db.reflect()`)
- **Reason:** AsyncEngine requires async reflection, `__getattr__` is sync
- **Benefit:** Explicit, predictable, fast cache access after reflection

### Phase 6: xtra() Filtering ✅ COMPLETE (Implemented Early in Phase 3)

**Status:** All items completed in Phase 3

**Note:** This phase was implemented early alongside CRUD operations in Phase 3.

1. **✅ Table.xtra() implementation**
   - Return new Table instance with filters
   - Don't mutate original
   - Implemented in Phase 3 (table.py:71-89)

2. **✅ Apply xtra filters to all operations**
   - Add WHERE clauses to selects
   - Auto-set values on insert
   - Filter updates/deletes
   - Raise NotFoundError on violations
   - Applied in all CRUD methods

3. **✅ Tests**
   - Set xtra filters → Tested in Phase 3
   - Verify isolation behavior → Tested in Phase 3
   - Test NotFoundError cases → Tested in Phase 3
   - **Tests included in Phase 3 test suite**

**See Phase 3 for complete implementation and tests.**

### Phase 7: Views Support ✅ COMPLETE

**Status:** All items completed

**Notes:**
- upsert() was moved to Phase 3 ✅
- with_pk parameter was implemented in Phase 3 ✅

1. **✅ Views support**
   - `db.create_view()` implementation with replace parameter
   - ViewAccessor class for db.v (cache-only sync access)
   - Read-only View class (inherits from Table, blocks write operations)
   - View reflection with `db.reflect_view()`
   - Views accessible via `db.v.viewname`

2. **✅ ~~with_pk parameter~~** Already implemented in Phase 3
   - All functionality completed in Phase 3

3. **✅ Tests**
   - View creation with SQL → 3 tests
   - View querying (SELECT, GET, LOOKUP) → 4 tests
   - Read-only enforcement (blocks INSERT/UPDATE/DELETE) → 4 tests
   - View drop → 1 test
   - View accessor (db.v.viewname) → 4 tests
   - View reflection → 2 tests
   - Views with dataclass support → 1 test
   - **19 new tests, all passing**

**Deliverables:**
- `db.create_view(name, sql, replace=False)` method
- `db.reflect_view(name)` for existing views
- ViewAccessor with cache-only sync access
- View.drop() implementation
- Read-only enforcement (blocks all write operations)
- Full dataclass support for views
- 161 total passing tests (142 + 19 new)
- Documentation and examples

**What Works Now:**
```python
# Create view
view = await db.create_view(
    "active_users",
    "SELECT * FROM users WHERE active = 1"
)

# Query view (read-only operations)
all_active = await view()
user = await view[1]  # Uses first column as pseudo-PK
found = await view.lookup(email="alice@example.com")

# Dynamic access
view = db.v.active_users  # Cache hit after create_view()

# Reflect existing views
await db.reflect_view('existing_view')
view = db.v.existing_view

# Views with dataclass
ViewDC = view.dataclass()
results = await view()  # Returns dataclass instances

# Drop view
await view.drop()
```

### Phase 8: Polish & Utilities ✅ COMPLETE

**Status:** All items completed

1. **✅ Error handling improvements**
   - Enhanced exception system with 6 specific exception types
   - `DeeBaseError` base class
   - `NotFoundError` with table_name and filters attributes
   - `IntegrityError` with constraint type detection
   - `ValidationError` with field and value attributes
   - `SchemaError` with table and column names
   - `ConnectionError` with sanitized database URL
   - `InvalidOperationError` for invalid operations
   - Wrapped all SQLAlchemy exceptions with better context
   - Improved error messages throughout codebase

2. **✅ Code generation features**
   - `dataclass_src()` for generating Python source code from dataclasses
   - `create_mod()` for exporting multiple dataclasses to .py files
   - `create_mod_from_tables()` convenience function for tables
   - Smart import detection and deduplication
   - Handles all Python types (Optional, datetime, dict, etc.)

3. **✅ Documentation**
   - Complete API reference (docs/api_reference.md)
   - Migration guide from fastlite (docs/migrating_from_fastlite.md)
   - Updated implemented.md with Phase 8 features
   - Enhanced complete_example.py with error handling demo
   - All examples tested and working

**Deliverables:**
- 6 new exception types with rich attributes
- 3 new code generation functions
- 2 comprehensive documentation files
- Updated examples with error handling
- 161 total passing tests
- Production-ready error handling

**🎉 ALL 8 PHASES COMPLETE! PROJECT FINISHED! 🎉**

## Testing Strategy

Each phase includes tests:
- Unit tests for individual methods
- Integration tests for full workflows
- Test with in-memory SQLite (`:memory:`)
- Verify async behavior (proper awaiting)
- Test error conditions
- Use pytest-asyncio for async test support

## FastLite API Reference

### Return Type Logic

**db.q()** - Always returns list of dicts
- Raw SQL queries have no schema context
- Always returns: `[{'col1': val1, 'col2': val2}, ...]`

**Table methods** - Context-dependent based on dataclass association:

**Without a dataclass (default):**
```python
albums(limit=1)       # Returns [{'AlbumId': 1, 'Title': '...'}]
albums[1]             # Returns {'AlbumId': 1, 'Title': '...'}
albums.insert({...})  # Returns {'AlbumId': 1, ...}
```

**With a dataclass (after calling `.dataclass()` or `db.create(SomeClass)`):**
```python
albums(limit=1)       # Returns [Album(AlbumId=1, Title='...')]
albums[1]             # Returns Album(AlbumId=1, Title='...')
albums.insert({...})  # Returns Album(AlbumId=1, ...)
```

### When Tables Get Dataclasses

A table has an associated dataclass when:
1. Created via `db.create(SomeClass)` - the class becomes the table's dataclass
2. You explicitly call `table.dataclass()` - generates and associates a dataclass
3. Otherwise, no dataclass exists and everything returns dicts

This provides **opt-in type safety**:
- Start simple with dicts for quick scripting
- Add type safety by calling `.dataclass()` when you need it
- The library "remembers" the dataclass and uses it consistently afterward

## Dependencies

Required packages:
- `sqlalchemy[asyncio]` - Core ORM/async support
- `aiosqlite` - Async SQLite driver
- `asyncpg` - Async PostgreSQL driver (for future Postgres support)
- `pytest` - Testing framework
- `pytest-asyncio` - Async test support

## Next Steps

1. ✅ Create project structure
2. Start Phase 1: Core Infrastructure
   - Implement Database class with basic functionality
   - Setup type mapping
   - Create test infrastructure
3. Build incrementally with tests at each phase
