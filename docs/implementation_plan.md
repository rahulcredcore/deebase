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
   - New phase8_polish_utilities.py example demonstrating all Phase 8 features
   - All examples tested and working

**Deliverables:**
- 6 new exception types with rich attributes
- 3 new code generation functions
- 2 comprehensive documentation files
- Comprehensive Phase 8 example file (examples/phase8_polish_utilities.py)
- 161 total passing tests
- Production-ready error handling

---

### Phase 9: Transaction Support ✅ COMPLETE

**Status:** All items completed

**Goal:** Add support for atomic multi-operation database transactions with automatic commit/rollback handling.

1. **✅ Transaction context manager**
   - `db.transaction()` context manager for multi-operation transactions
   - Automatic session sharing across operations within transaction scope
   - Thread-safe implementation using Python's `contextvars`
   - Automatic commit on successful completion
   - Automatic rollback on any exception
   - Clean API - no explicit `commit=False` parameters needed

2. **✅ CRUD method refactoring**
   - Refactored all CRUD methods to support transactions
   - Added `_session_scope()` helper for automatic session detection
   - Write operations: `insert()`, `update()`, `upsert()`, `delete()`
   - Read operations: `__call__()`, `__getitem__()`, `lookup()`
   - DDL operations: `drop()`
   - All methods auto-detect active transaction context
   - Backward compatible - non-transactional operations still auto-commit

3. **✅ Comprehensive testing**
   - 22 new comprehensive transaction tests (all passing)
   - Test categories:
     - Transaction setup/teardown and rollback behavior
     - Insert operations in transactions
     - Update operations in transactions
     - Upsert operations in transactions
     - Delete operations in transactions
     - Read operations in transactions (consistent reads)
     - Mixed CRUD operations
     - Edge cases and error conditions
   - Total: 183 passing tests (161 + 22)

4. **✅ Documentation and examples**
   - Comprehensive example: `examples/transactions.py`
   - Demonstrates 8 real-world scenarios:
     - Basic transaction usage
     - Automatic rollback on exception
     - Money transfer (read-modify-write pattern)
     - Failed transfer with business logic rollback
     - Batch operations
     - Constraint violation rollback
     - Mixed CRUD operations
     - Backward compatibility

**Features:**
- **Automatic Detection**: Operations automatically participate in active transactions
- **Clean API**: Simple `async with db.transaction():` wrapper
- **Atomic Operations**: All operations succeed together or fail together
- **Consistent Reads**: Read operations see transaction snapshot
- **Error Handling**: Automatic rollback on any exception type
- **Backward Compatible**: Zero breaking changes, existing code continues to work
- **Thread-Safe**: Uses contextvars for proper async context isolation

**Use Cases:**
- Money transfers and financial operations
- Multi-table updates that must stay consistent
- Batch operations that should succeed/fail together
- Complex business logic requiring atomicity
- Read-modify-write patterns with race condition protection

**Implementation Details:**
- Added `_active_session` ContextVar to database.py for session tracking
- Created `db.transaction()` async context manager
- Refactored Table class with `_session_scope()` helper
- All CRUD methods check for active session before creating new one
- Commit/rollback only managed when no active transaction
- 100% backward compatible - all 161 existing tests still pass

**Deliverables:**
- Transaction context manager in Database class
- Refactored CRUD methods with transaction support
- 22 comprehensive transaction tests (100% passing)
- Practical example file: examples/transactions.py
- 183 total passing tests
- Zero breaking changes

---

### Phase 10: Enhanced Create with Foreign Keys & Defaults ✅ COMPLETE

**Status:** Complete

**Goal:** Enhance `create()` to support foreign keys via type annotations and extract default values from class definitions, following Python's native patterns.

**Design Principle:** Use Python's existing features (type annotations, class defaults) rather than adding many parameters.

1. **ForeignKey type annotation**
   - New `ForeignKey[T, "table.column"]` generic type
   - Parses reference string: `"users"` → `users.id`, `"users.email"` → `users.email`
   - Generates SQLAlchemy `ForeignKeyConstraint` during table creation
   - Example:
     ```python
     from deebase import ForeignKey

     class Post:
         id: int
         author_id: ForeignKey[int, "users"]      # → FK to users.id
         category_id: ForeignKey[int, "categories.id"]  # → FK to categories.id
     ```

2. **Extract defaults from class definitions**
   - Support both regular classes and dataclasses
   - Regular class: `status: str = "active"` → SQL `DEFAULT 'active'`
   - Dataclass: `status: str = "draft"` → SQL `DEFAULT 'draft'`
   - Only extract immutable scalar defaults (str, int, float, bool)
   - Skip `field(default_factory=...)` - works Python-side, no SQL default
   - Skip mutable defaults (dict, list) - too complex for SQL defaults

3. **New create() parameters**
   - `if_not_exists: bool = False` - Use `CREATE TABLE IF NOT EXISTS`
   - `replace: bool = False` - Drop table first, then create

4. **Input/Output behavior unchanged**
   - Regular class input → dict rows
   - Dataclass input → dataclass instance rows
   - `.dataclass()` switches to dataclass output
   - This phase only affects schema generation, not row handling

5. **What we're NOT adding**
   - `transform` - That's migrations territory (alembic)
   - `hash_id` / `hash_id_columns` - Niche, can add later if needed
   - `not_null` parameter - Use non-Optional types
   - `defaults` parameter - Use class defaults
   - `column_order` - Python 3.7+ preserves order

6. **Tests** (~20 new tests)
   - ForeignKey type parsing
   - FK constraint creation
   - FK constraint enforcement (insert fails with invalid FK)
   - Scalar defaults extraction (str, int, float, bool)
   - Mutable defaults skipped (dict, list)
   - Dataclass with default_factory skipped
   - if_not_exists behavior
   - replace behavior
   - Regular class vs dataclass input

**Deliverables:**
- `ForeignKey` generic type in types.py
- `extract_defaults()` function in dataclass_utils.py
- Enhanced `create()` method with `if_not_exists` and `replace` parameters
- 36 new tests (219 total passing tests)
- Updated documentation

**Key Implementation Details:**
- `ForeignKey[T, "table"]` type annotation for FK columns
- Automatic extraction of scalar defaults from class definitions
- `if_not_exists=True` for safe table creation (no error if exists)
- `replace=True` to drop and recreate tables
- ForeignKeyConstraint generation in SQLAlchemy
- Mutable defaults (dict, list, default_factory) are skipped for SQL defaults
- Input/output behavior unchanged (regular class → dicts, dataclass → instances)

---

### Phase 11: FK Relationship Navigation ✅ COMPLETE

**Status:** Complete

**Goal:** Enable navigation from tables to related records via foreign keys, with clean syntax for forward navigation and power-user API for reverse lookups.

**Design Decisions:**
1. `get_children()` accepts both string table name and Table object
2. Parent not found returns `None` (not NotFoundError)
3. Return type respects target table's dataclass setting
4. FK metadata sourced from both annotations (`create()`) and SQLAlchemy reflection

**API Overview:**

```python
from deebase import Database, ForeignKey

class User:
    id: int
    name: str

class Post:
    id: int
    author_id: ForeignKey[int, "user"]
    title: str

users = await db.create(User, pk='id')
posts = await db.create(Post, pk='id')

# 1. FK metadata property
posts.foreign_keys
# -> [{'column': 'author_id', 'references': 'user.id'}]

# 2. Clean forward navigation via fk accessor
post = await posts[1]
author = await posts.fk.author_id(post)  # -> User dict/dataclass or None

# 3. Verbose forward navigation (documented API)
author = await posts.get_parent(post, "author_id")

# 4. Reverse navigation - power user API
user = await users[1]
user_posts = await users.get_children(user, "posts", "author_id")  # -> [Post, ...]
# Also accepts Table object:
user_posts = await users.get_children(user, posts, "author_id")
```

**Implementation Details:**

1. **`table.foreign_keys` property**
   - Returns list of FK definitions: `[{'column': str, 'references': 'table.column'}, ...]`
   - Populated during `create()` from `ForeignKey[T, "table"]` annotations
   - Populated during reflection from SQLAlchemy FK inspection
   - Cached on Table instance

2. **`FKAccessor` class (table.fk)**
   - Accessed via `table.fk.column_name(record)`
   - `__getattr__` returns a callable that takes a record
   - Returns awaitable (async def internally)
   - Validates FK column exists, raises `ValidationError` if not

3. **`table.get_parent(record, fk_column)` method**
   - Extract FK value from record
   - If FK value is None, return None (nullable FK)
   - Look up referenced table from FK metadata
   - Fetch parent via `parent_table[fk_value]`
   - If parent not found, return None (dangling FK)
   - Respect target table's dataclass setting for return type

4. **`table.get_children(record, child_table, fk_column)` method**
   - Accept child_table as string or Table object
   - If string, look up in `db._tables` cache
   - Extract PK value from record
   - Query child table with `fk_column = pk_value`
   - Return list of matching records (empty list if none)
   - Respect child table's dataclass setting

**What We're NOT Implementing:**
- Connected record wrapper (`post.fk.author_id` on record itself) - maybe later
- Auto-discovery of reverse relationships
- `table.children.other_table` style accessor
- Automatic lazy loading (causes N+1 problems)
- ORM-style `relationship()` definitions
- Cascade handling (use database constraints)
- Eager loading (use `db.q()` with JOINs)

**Tests (~20 new tests):**
- `foreign_keys` property from `create()` with FK annotations
- `foreign_keys` property from reflection
- `fk.column_name(record)` forward navigation
- `get_parent()` with valid FK
- `get_parent()` with None FK value (nullable)
- `get_parent()` with dangling FK (returns None)
- `get_parent()` with invalid column (ValidationError)
- `get_children()` with string table name
- `get_children()` with Table object
- `get_children()` returns empty list when no children
- `get_children()` with invalid table (SchemaError)
- Return type respects dataclass setting
- Works with composite PKs
- Works with reflected tables

**Deliverables:**
- `FKAccessor` class in new file or table.py
- `table.foreign_keys` property
- `table.fk` accessor
- `table.get_parent()` method
- `table.get_children()` method
- FK metadata storage during create/reflect
- ~20 new tests
- Phase 11 example file
- Updated documentation

---

### Phase 12: Indexes ✅ COMPLETE

**Status:** Complete

**Goal:** Support explicit indexes for query optimization.

**Note:** FTS was removed from scope as it's SQLite-only. JOINs are handled elegantly via views (see [best-practices.md](best-practices.md#using-views-for-joins-and-ctes)).

**API:**

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

**Implementation Details:**

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

**Tests (~20-25 new tests):**
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

**Deliverables:**
- `Index` class exported from deebase
- `indexes` parameter on `db.create()`
- `table.create_index()` method
- `table.drop_index()` method
- `table.indexes` property
- ~20-25 new tests
- Phase 12 example file
- Documentation updates

---

### Phase 13: Command-Line Interface (CLI) ✅ COMPLETE

**Status:** Complete

**Goal:** Provide a Click-based CLI for database management, table creation, code generation, and migration preparation. The CLI produces Python code that gets recorded for future migration replay.

**Design Philosophy:**
- CLI commands are **input** that generate **Python code**
- Generated code uses the DeeBase API (`db.create()`, `db.q()`, etc.)
- Three outputs per command: (1) immediate execution, (2) models file, (3) migration file
- Architecture is migration-ready even though migrations come in Phase 14

#### Installation

CLI installed via pyproject.toml entry point:

```toml
[project.scripts]
deebase = "deebase.cli:main"

[project.optional-dependencies]
cli = ["click>=8.0", "python-dotenv>=1.0", "toml>=0.10"]
```

#### Project Structure

```
project/
├── .deebase/
│   ├── config.toml          # Project settings (tracked)
│   ├── .env                  # Secrets: connection strings (gitignored)
│   └── state.json            # Current migration state (tracked)
├── data/
│   └── app.db               # SQLite files (gitignored)
├── migrations/
│   └── 0000-initial.py      # Migration files (tracked)
├── myapp/                   # User's package (if --package used)
│   └── models/
│       └── tables.py        # Generated models (tracked)
└── models/                  # Standalone mode models
    └── tables.py
```

#### Command Structure

**Initialization Commands:**

```bash
# Initialize standalone project
deebase init
# Creates: .deebase/, migrations/, models/, data/

# Initialize with existing Python package
deebase init --package myapp
# Creates: .deebase/, migrations/, data/
# Models go to: myapp/models/tables.py

# Initialize new Python package
deebase init --new-package myapp
# Creates: myapp/ package structure + deebase files

# Initialize for PostgreSQL instead of SQLite
deebase init --postgres
```

**Database Commands:**

```bash
# Show database info (connection, tables, views, version)
deebase db info

# Execute raw SQL (recorded in migration)
deebase sql "CREATE VIEW active_users AS SELECT * FROM users WHERE active = 1"

# Interactive SQL shell (not recorded)
deebase db shell
```

**Table Commands:**

```bash
# Create table with field:type[:modifier] syntax
deebase table create users \
    id:int \
    name:str \
    email:str:unique \
    bio:Text \
    metadata:dict \
    status:str:default=active \
    created_at:datetime \
    --pk id

# With foreign keys
deebase table create posts \
    id:int \
    author_id:int:fk=users \
    title:str \
    content:Text \
    --pk id \
    --index author_id

# List all tables
deebase table list

# Show table schema
deebase table schema users

# Drop table (with confirmation)
deebase table drop users
```

**Field Type Syntax:**

```
field:type[:modifier[:modifier...]]

Types:
  int, str, float, bool, bytes
  Text          - Unlimited text
  dict          - JSON column
  datetime, date, time

Modifiers:
  :unique       - UNIQUE constraint
  :nullable     - Optional field (NULL allowed)
  :default=val  - Default value
  :fk=table     - Foreign key to table.id
  :fk=table.col - Foreign key to table.column
```

**Index Commands:**

```bash
# Create index
deebase index create posts author_id
deebase index create posts author_id,created_at --name idx_author_date
deebase index create users email --unique

# List indexes on table
deebase index list posts

# Drop index
deebase index drop idx_author_date
```

**View Commands:**

```bash
# Create view from SQL
deebase view create active_users --sql "SELECT * FROM users WHERE active = 1"

# Reflect existing view (after creating with db sql)
deebase view reflect active_users

# List views
deebase view list

# Drop view
deebase view drop active_users
```

**Code Generation Commands:**

```bash
# Regenerate models from database
deebase codegen                    # All tables
deebase codegen users posts        # Specific tables
deebase codegen --output myapp/models/tables.py
```

**Migration Prep Commands (for Phase 14):**

```bash
# Seal current migration (freeze it, start new one)
deebase migrate seal "description"

# Show migration status (current version, unsealed changes)
deebase migrate status
```

#### How Commands Generate Code

When user runs:
```bash
$ deebase table create users id:int name:str email:str:unique --pk id
```

**1. Parse and generate Python class:**
```python
class User:
    id: int
    name: str
    email: str  # unique constraint handled separately
```

**2. Execute immediately:**
```python
await db.create(User, pk='id', indexes=[Index('ix_user_email', 'email', unique=True)])
```

**3. Append to models file (`models/tables.py`):**
```python
@dataclass
class User:
    id: Optional[int] = None
    name: str = ""
    email: str = ""  # unique
```

**4. Append to migration file (`migrations/0000-initial.py`):**
```python
# In upgrade() function:
class User:
    id: int
    name: str
    email: str

await db.create(User, pk='id', indexes=[Index('ix_user_email', 'email', unique=True)])
```

#### Config Files

**.deebase/config.toml:**
```toml
[project]
name = "myapp"
version = "0.1.0"

[database]
type = "sqlite"                    # or "postgres"
sqlite_path = "data/app.db"
# postgres from .env: DATABASE_URL

[models]
output = "models/tables.py"        # or "myapp/models/tables.py"
module = "models.tables"           # import path

[migrations]
directory = "migrations"
auto_seal = false                  # seal after each command?
```

**.deebase/.env:**
```bash
# SQLite (optional, can use config.toml path)
DATABASE_URL=sqlite+aiosqlite:///data/app.db

# PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/dbname
```

**.deebase/state.json:**
```json
{
  "current_migration": "0000-initial",
  "sealed": false,
  "db_version": 0
}
```

#### Implementation Details

1. **CLI Module Structure:**
   ```
   src/deebase/
   ├── cli/
   │   ├── __init__.py      # Click group and main()
   │   ├── init_cmd.py      # deebase init
   │   ├── db_cmd.py        # deebase db info/shell/sql
   │   ├── table_cmd.py     # deebase table create/list/schema/drop
   │   ├── index_cmd.py     # deebase index create/list/drop
   │   ├── view_cmd.py      # deebase view create/reflect/list/drop
   │   ├── codegen_cmd.py   # deebase codegen
   │   ├── migrate_cmd.py   # deebase migrate seal/status
   │   ├── parser.py        # field:type parser
   │   ├── generator.py     # Python code generator
   │   └── state.py         # Migration state management
   ```

2. **Async Wrapper:**
   Click is synchronous, so we wrap async calls:
   ```python
   import asyncio

   def run_async(coro):
       return asyncio.run(coro)

   @click.command()
   def create_table(...):
       run_async(_create_table_async(...))
   ```

3. **Field Parser:**
   ```python
   def parse_field(field_spec: str) -> FieldDefinition:
       """Parse 'name:str:unique:default=foo' into FieldDefinition"""
       parts = field_spec.split(':')
       name = parts[0]
       type_ = parts[1]
       modifiers = parts[2:]
       # Returns structured field definition
   ```

4. **Code Generator:**
   ```python
   def generate_class(name: str, fields: list[FieldDefinition]) -> str:
       """Generate Python class source code"""

   def generate_create_call(name: str, fields: list, pk: str, indexes: list) -> str:
       """Generate db.create() call"""
   ```

5. **Migration File Writer:**
   ```python
   def append_to_migration(code: str, state: MigrationState):
       """Append operation to current unsealed migration"""
   ```

#### Tests (~40 new tests)

**CLI Infrastructure:**
- Click command registration
- Async wrapper functionality
- Config file loading
- State file management

**Init Command:**
- `deebase init` creates correct structure
- `deebase init --package myapp` integrates with existing package
- `deebase init --postgres` sets correct config
- Idempotent (safe to run twice)

**Table Commands:**
- Parse simple field:type syntax
- Parse all type modifiers (:unique, :nullable, :default, :fk)
- Generate correct Python class
- Execute and record in migration
- List tables from database
- Show table schema
- Drop table with migration record

**Index Commands:**
- Create simple and composite indexes
- Create unique indexes
- List indexes on table
- Drop index with migration record

**View Commands:**
- Create view from SQL
- Reflect existing view
- List views
- Drop view

**Code Generation:**
- Generate models from database
- Correct dataclass formatting
- Handle all column types

**Migration Prep:**
- Seal migration creates new file
- Status shows correct state

**Integration:**
- Full workflow: init → create tables → indexes → codegen
- Temp directory isolation for tests

#### Deliverables

- `deebase.cli` package with Click commands
- Field:type parser
- Python code generator
- Migration file writer (sealed/unsealed workflow)
- State management
- 57 new tests (337 total passing)
- CLI documentation (docs/cli_reference.md)
- Example workflows (examples/phase13_cli.py, examples/complete_cli_example.py)

#### Dependencies (New)

```toml
[project.optional-dependencies]
cli = [
    "click>=8.0",
    "python-dotenv>=1.0",
    "pyyaml>=6.0",
]
```

---

### Phase 14: Migrations (Planned)

**Status:** Planned

**Goal:** Complete the migration system with `up`/`down` execution. Phase 13 already implemented the sealed/unsealed workflow and file generation. This phase adds the runtime to actually execute migrations.

**Design Decision:** No Alembic. Simple custom runner following fastmigrate patterns. The existing migration files use DeeBase's async API, which works well with a simple runner (~100-150 lines).

#### What Phase 13 Already Provides

- Migration file generation (`migrations/NNN_*.py`)
- Sealed/unsealed workflow (`deebase migrate seal "description"`)
- Migration status (`deebase migrate status`)
- New migration creation (`deebase migrate new "description"`)
- CLI commands append to current unsealed migration

#### What Phase 14 Will Add

**New CLI Commands:**

```bash
# Apply all pending migrations
deebase migrate up

# Apply up to specific version
deebase migrate up --to 003

# Rollback last migration
deebase migrate down

# Rollback to specific version
deebase migrate down --to 001
```

**Version Tracking Table:**

```sql
CREATE TABLE _deebase_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Migration File Format (Already Implemented)

```python
# migrations/001_initial_schema.py
"""Migration: initial_schema

Created: 2024-01-15 10:30:00
DeeBase migration file - uses async DeeBase API.
"""


async def up(db):
    """Apply migration."""
    class User:
        id: int
        name: str
        email: str

    await db.create(User, pk='id', indexes=['email'])

    class Post:
        id: int
        author_id: ForeignKey[int, "user"]
        title: str

    await db.create(Post, pk='id')


async def down(db):
    """Revert migration."""
    await db.t.post.drop()
    await db.t.user.drop()
```

#### Implementation Details

1. **Migration Runner (~100-150 lines):**
   ```python
   class MigrationRunner:
       def __init__(self, db: Database, migrations_dir: Path):
           self.db = db
           self.migrations_dir = migrations_dir

       async def up(self, to_version: int = None):
           """Apply pending migrations up to target version."""
           await self._ensure_version_table()
           current = await self._get_current_version()
           pending = self._discover_migrations(after=current, up_to=to_version)

           for migration in pending:
               async with self.db.transaction():
                   await migration.up(self.db)
                   await self._record_migration(migration.version, migration.name)

       async def down(self, to_version: int = None):
           """Rollback migrations down to target version."""
           current = await self._get_current_version()
           to_rollback = self._discover_migrations(after=to_version, up_to=current)

           for migration in reversed(to_rollback):
               async with self.db.transaction():
                   await migration.down(self.db)
                   await self._remove_migration(migration.version)

       async def status(self) -> dict:
           """Get migration status."""
           await self._ensure_version_table()
           applied = await self._get_applied_migrations()
           available = self._discover_migrations()
           pending = [m for m in available if m.version not in applied]
           return {
               "current_version": max(applied) if applied else 0,
               "applied": applied,
               "pending": pending,
           }
   ```

2. **Version Table Management:**
   ```python
   async def _ensure_version_table(self):
       """Create migrations table if not exists."""
       await self.db.q("""
           CREATE TABLE IF NOT EXISTS _deebase_migrations (
               version INTEGER PRIMARY KEY,
               name TEXT NOT NULL,
               applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
           )
       """)

   async def _get_current_version(self) -> int:
       """Get highest applied version."""
       result = await self.db.q("SELECT MAX(version) as v FROM _deebase_migrations")
       return result[0]['v'] or 0

   async def _record_migration(self, version: int, name: str):
       """Record applied migration."""
       await self.db.q(
           f"INSERT INTO _deebase_migrations (version, name) VALUES ({version}, '{name}')"
       )

   async def _remove_migration(self, version: int):
       """Remove migration record (for rollback)."""
       await self.db.q(f"DELETE FROM _deebase_migrations WHERE version = {version}")
   ```

3. **Migration Discovery:**
   ```python
   def _discover_migrations(self, after: int = 0, up_to: int = None) -> list:
       """Find migration files in order."""
       migrations = []
       for path in sorted(self.migrations_dir.glob("*.py")):
           if path.name.startswith("_"):
               continue
           # Parse NNN_name.py format
           match = re.match(r"(\d+)_(.+)\.py", path.name)
           if match:
               version = int(match.group(1))
               if version > after and (up_to is None or version <= up_to):
                   module = self._load_migration(path)
                   migrations.append(Migration(version, match.group(2), module))
       return migrations

   def _load_migration(self, path: Path):
       """Import migration module."""
       spec = importlib.util.spec_from_file_location(path.stem, path)
       module = importlib.util.module_from_spec(spec)
       spec.loader.exec_module(module)
       return module
   ```

#### CLI Integration

Update `src/deebase/cli/migrate_cmd.py`:

```python
@migrate.command('up')
@click.option('--to', type=int, help='Target version')
def up(to: int):
    """Apply pending migrations."""
    run_async(_migrate_up(to))

@migrate.command('down')
@click.option('--to', type=int, help='Target version to rollback to')
def down(to: int):
    """Rollback migrations."""
    run_async(_migrate_down(to))
```

#### What We're NOT Implementing

- **Auto-diff generation** - Too complex, better to use CLI commands
- **Alembic** - Overkill for this use case
- **Schema comparison** - Manual migrations are explicit and clear
- **Concurrent migration locking** - Keep simple, use external locks if needed

#### Tests (~20 new tests)

- Version table creation
- `migrate up` applies single migration
- `migrate up` applies multiple migrations in order
- `migrate up --to N` stops at target version
- `migrate down` rolls back last migration
- `migrate down --to N` rolls back to target version
- Migration discovery finds files in order
- Skips already-applied migrations
- Error during migration rolls back transaction
- Status shows correct pending/applied counts
- Works with SQLite
- Works with PostgreSQL (if testing infrastructure exists)

#### Deliverables

- `MigrationRunner` class (~100-150 lines)
- Updated CLI commands (up, down)
- Version table management
- ~20 new tests
- Updated documentation

#### FastMigrate Compatibility

Following fastmigrate patterns:
- `NNN_description.py` naming convention
- Version tracked in database table
- Python migration scripts with `up()` and `down()` functions
- Sequential execution order
- Transaction per migration
- Rollback support

**Differences from fastmigrate:**
- Async DeeBase API (async def up/down)
- PostgreSQL support in addition to SQLite
- Integrated with DeeBase CLI workflow

---

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
