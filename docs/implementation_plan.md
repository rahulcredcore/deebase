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

### Phase 14: Migrations (Complete)

**Status:** ✅ Complete

**Goal:** Complete the migration system with `up`/`down` execution. Phase 13 already implemented the sealed/unsealed workflow and file generation. This phase adds the runtime to actually execute migrations.

**Design Decision:** No Alembic. Simple custom runner following fastmigrate patterns. The existing migration files use DeeBase's async API, which works well with a simple runner (~100-150 lines).

#### FastMigrate Alignment

We align with fastmigrate conventions where practical, with intentional divergences for async/multi-database support:

| Aspect | FastMigrate | DeeBase | Rationale |
|--------|-------------|---------|-----------|
| File naming | `NNNN-description.ext` | `NNNN-description.py` | **Aligned** - 4-digit, hyphen separator for familiarity |
| Script formats | `.sql`, `.py`, `.sh` | `.py` only | Python-only; use `await db.q()` for raw SQL within migrations |
| Version table | `_meta` (single row) | `_deebase_migrations` (multi-row) | Full migration history with timestamps for audit trail |
| Rollback | Not supported | `downgrade()` functions | Useful for development; differentiator |
| Execution | Subprocess | In-process import | Required for async `await` calls |
| Database | SQLite only | SQLite + PostgreSQL | Multi-database support |
| API | Sync | Async | Modern Python async/await |

#### What Phase 13 Already Provides

- Migration file generation (`migrations/NNNN-*.py`)
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
deebase migrate up --to 0003

# Rollback last migration
deebase migrate down

# Rollback to specific version
deebase migrate down --to 0001

# Create timestamped database backup (SQLite only)
deebase db backup
```

**Version Tracking Table:**

```sql
-- Multi-row table for full migration history (differs from fastmigrate's single-row _meta)
CREATE TABLE _deebase_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

This provides:
- Full audit trail of applied migrations
- Timestamp of when each migration was applied
- Easy rollback tracking (delete row on down)
- Query-able migration history

#### Migration File Format

```python
# migrations/0001-initial-schema.py
"""Migration: initial-schema

Auto-generated by deebase CLI.
"""

from deebase import Database, Text, ForeignKey, Index


async def upgrade(db: Database):
    """Apply this migration."""
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

    # Raw SQL also supported via db.q()
    await db.q("CREATE INDEX idx_post_title ON post(title)")


async def downgrade(db: Database):
    """Reverse this migration."""
    await db.t.post.drop()
    await db.t.user.drop()
```

**File Naming Convention:**
- Pattern: `NNNN-description.py` (4-digit version, hyphen separator)
- Examples: `0001-initial-schema.py`, `0002-add-comments.py`, `0010-user-roles.py`
- Matches fastmigrate convention for familiarity

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
                   await migration.module.upgrade(self.db)
                   await self._record_migration(migration.version, migration.name)
               print(f"Applied: {migration.version:04d}-{migration.name}")

       async def down(self, to_version: int = 0):
           """Rollback migrations down to target version."""
           current = await self._get_current_version()
           to_rollback = self._discover_migrations(after=to_version, up_to=current)

           for migration in reversed(to_rollback):
               async with self.db.transaction():
                   await migration.module.downgrade(self.db)
                   await self._remove_migration(migration.version)
               print(f"Rolled back: {migration.version:04d}-{migration.name}")

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

   async def _get_applied_migrations(self) -> list[int]:
       """Get all applied migration versions."""
       result = await self.db.q("SELECT version FROM _deebase_migrations ORDER BY version")
       return [r['version'] for r in result]

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
           # Parse NNNN-name.py format (fastmigrate convention)
           match = re.match(r"(\d{4})-(.+)\.py", path.name)
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

4. **Database Backup (SQLite and PostgreSQL):**

   **SQLite backup** - Uses native Python API:
   ```python
   def create_backup_sqlite(db_path: Path) -> Path:
       """Create timestamped backup using SQLite's backup mechanism."""
       import sqlite3
       from datetime import datetime

       timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
       backup_path = db_path.with_suffix(f".{timestamp}.backup")

       # Use SQLite's backup API for consistency
       source = sqlite3.connect(db_path)
       dest = sqlite3.connect(backup_path)
       source.backup(dest)
       source.close()
       dest.close()

       return backup_path
   ```

   **PostgreSQL backup** - Uses `pg_dump` CLI tool:
   ```python
   import shutil
   import subprocess
   from datetime import datetime
   from pathlib import Path

   def create_backup_postgres(db_url: str, output_dir: Path = None) -> Path:
       """Create timestamped backup using pg_dump.

       Args:
           db_url: PostgreSQL connection URL
           output_dir: Directory for backup file (default: current directory)

       Returns:
           Path to the backup file

       Raises:
           RuntimeError: If pg_dump is not installed or fails
       """
       # Check if pg_dump is available
       if shutil.which("pg_dump") is None:
           raise RuntimeError(
               "pg_dump not found. Please install PostgreSQL client tools:\n"
               "  - macOS: brew install postgresql\n"
               "  - Ubuntu/Debian: apt install postgresql-client\n"
               "  - Windows: Install PostgreSQL and add bin/ to PATH"
           )

       timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
       output_dir = output_dir or Path.cwd()
       backup_path = output_dir / f"backup_{timestamp}.sql"

       # pg_dump accepts connection URL directly
       result = subprocess.run(
           ["pg_dump", db_url, "-f", str(backup_path)],
           capture_output=True,
           text=True,
       )

       if result.returncode != 0:
           raise RuntimeError(f"pg_dump failed: {result.stderr}")

       return backup_path
   ```

5. **Database Compatibility Helper:**
   ```python
   async def enable_foreign_keys(db: Database) -> None:
       """Enable foreign key enforcement (SQLite only, no-op on PostgreSQL).

       SQLite has FK enforcement disabled by default. PostgreSQL always enforces FKs.
       Call this after creating a Database connection if using SQLite with FKs.

       Example:
           db = Database("sqlite+aiosqlite:///app.db")
           await db.enable_foreign_keys()
       """
       if "sqlite" in db.engine.dialect.name:
           await db.q("PRAGMA foreign_keys = ON")
       # PostgreSQL: FKs are always enforced, no action needed
   ```

#### CLI Integration

Update `src/deebase/cli/migrate_cmd.py`:

```python
@migrate.command('up')
@click.option('--to', type=int, help='Target version (e.g., 3 for 0003)')
def up(to: int):
    """Apply pending migrations."""
    run_async(_migrate_up(to))

@migrate.command('down')
@click.option('--to', type=int, default=0, help='Target version to rollback to')
def down(to: int):
    """Rollback migrations."""
    run_async(_migrate_down(to))
```

Update `src/deebase/cli/db_cmd.py`:

```python
@db.command('backup')
def backup():
    """Create timestamped database backup.

    SQLite: Creates a .backup file using native backup API.
    PostgreSQL: Runs pg_dump (must be installed).
    """
    run_async(_create_backup())

async def _create_backup():
    config = load_config()
    load_env()

    if config.database_type == 'sqlite':
        db_path = Path(config.sqlite_path)
        if not db_path.exists():
            click.echo(f"Error: Database file not found: {db_path}")
            sys.exit(1)
        backup_path = create_backup_sqlite(db_path)
        click.echo(f"Backup created: {backup_path}")

    elif config.database_type == 'postgres':
        db_url = config.get_database_url()
        try:
            backup_path = create_backup_postgres(db_url)
            click.echo(f"Backup created: {backup_path}")
        except RuntimeError as e:
            click.echo(f"Error: {e}")
            sys.exit(1)
```

#### Database Compatibility

This section documents SQLite-specific behaviors and how DeeBase handles cross-database compatibility.

| Behavior | SQLite | PostgreSQL | DeeBase Solution |
|----------|--------|------------|------------------|
| FK enforcement | Disabled by default | Always enabled | `db.enable_foreign_keys()` helper |
| List tables | `sqlite_master` | `information_schema` | `db.list_tables()` helper (optional) |
| Backup | `sqlite3.backup()` | `pg_dump` CLI | Detect dialect, use appropriate method |
| JSON storage | TEXT with serialization | Native JSON | SQLAlchemy handles transparently |
| Boolean storage | 0/1 integers | Native BOOLEAN | SQLAlchemy handles transparently |
| Auto-increment | `INTEGER PRIMARY KEY` | `SERIAL` / `IDENTITY` | SQLAlchemy handles transparently |

**Items already handled by SQLAlchemy (no action needed):**
- JSON serialization/deserialization
- Boolean type mapping
- Auto-increment primary keys
- Type-specific DDL generation

**Items added in Phase 14:**
- `db.enable_foreign_keys()` - Portable FK enforcement
- `deebase db backup` - Works for both databases

**Documentation updates needed:**
- Add PostgreSQL backup requirements to CLI reference
- Update examples to use `db.enable_foreign_keys()` instead of raw PRAGMA
- Add "Database Differences" section to best-practices.md

#### What We're NOT Implementing

- **Auto-diff generation** - Too complex, use CLI commands to generate migrations
- **Alembic** - Overkill; our simple runner is ~100-150 lines
- **Schema comparison** - Manual migrations are explicit and clear
- **Concurrent migration locking** - Keep simple, use external locks if needed
- **`.sql` / `.sh` migration scripts** - Python-only; use `db.q()` for raw SQL
- **`db.list_tables()` helper** - Low priority; users can query directly if needed

#### Tests (~30 new tests)

- Version table creation
- `migrate up` applies single migration
- `migrate up` applies multiple migrations in order
- `migrate up --to N` stops at target version
- `migrate down` rolls back last migration
- `migrate down --to N` rolls back to target version
- Migration discovery finds files in order (NNNN-name.py pattern)
- Skips already-applied migrations
- Error during migration rolls back transaction
- Status shows correct pending/applied counts
- Applied migrations recorded with timestamps
- Rollback removes migration record
- `db backup` creates timestamped backup (SQLite)
- `db backup` calls pg_dump (PostgreSQL, mocked)
- `db backup` errors gracefully if pg_dump missing
- `db.enable_foreign_keys()` runs PRAGMA on SQLite
- `db.enable_foreign_keys()` is no-op on PostgreSQL
- Works with SQLite
- Works with PostgreSQL (if testing infrastructure exists)

#### Deliverables

- `MigrationRunner` class (~100-150 lines)
- `Migration` dataclass for migration metadata
- CLI commands: `migrate up`, `migrate down`, `db backup`
- `db.enable_foreign_keys()` helper method
- `create_backup_sqlite()` and `create_backup_postgres()` functions
- Version table management
- ~30 new tests
- Updated documentation:
  - `docs/cli_reference.md` - Add backup command with pg_dump requirements
  - `docs/best-practices.md` - Add database compatibility section
  - `docs/api_reference.md` - Add `enable_foreign_keys()` method

#### Why These Design Choices

**Multi-row version table vs fastmigrate's single-row `_meta`:**
- Provides full audit trail (when was each migration applied?)
- Easier debugging ("which migrations are applied?")
- Clean rollback tracking (delete row vs decrement counter)
- Negligible overhead (migrations are rare operations)

**Python-only migrations (no `.sql`/`.sh`):**
- Async support requires in-process execution
- `await db.q("RAW SQL HERE")` handles raw SQL needs
- Consistent API - everything uses DeeBase methods
- Better error handling and transaction support

**Rollback support (unlike fastmigrate):**
- Essential for development workflow
- Enables safe experimentation
- Standard in most migration tools (Django, Rails, Alembic)
- Users can omit `downgrade()` if they don't need rollback

**PostgreSQL backup via pg_dump:**
- Standard PostgreSQL backup tool, well-documented
- Outputs portable SQL that can be restored with `psql`
- Error with helpful message if not installed (rather than silent failure)

---

### Phase 15: FastAPI Integration

**Status:** ✅ Complete

**Goal:** Add automatic REST API generation from deebase models. Users define `@dataclass` models with inline comments, and deebase generates documented FastAPI CRUD endpoints with Pydantic validation and FK existence checking.

#### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Documentation extraction | `fastcore.docments()` | Parses inline comments from dataclass source |
| Model requirement | `@dataclass` required | docments needs dataclass source for comment extraction |
| Validation layer | Pydantic models | Standard FastAPI pattern, automatic OpenAPI docs |
| FK validation | Application-level check | Validate before insert/update, better error messages than DB constraint failures |
| Route customization | Override dict + hooks + subclassing | Replace any auto-generated route with custom implementation |
| CLI integration | `deebase api init/serve/generate` | Scaffolding and development server |

#### Dependencies (New)

```toml
[project.optional-dependencies]
api = [
    "fastapi>=0.100.0",
    "pydantic>=2.0",
    "fastcore>=1.5.0",  # For docments()
    "uvicorn>=0.20.0",  # For deebase api serve
    "jinja2>=3.0",      # For HTML templates
]
```

#### Module Structure

```
src/deebase/
├── api/
│   ├── __init__.py           # Public exports: create_crud_router, CRUDRouter
│   ├── router.py             # CRUDRouter class and create_crud_router()
│   ├── models.py             # Pydantic model generation
│   ├── validators.py         # FK validation, custom validators
│   ├── exceptions.py         # ForeignKeyValidationError, etc.
│   └── docs.py               # docments integration
├── cli/
│   ├── api_cmd.py            # deebase api init/serve/generate (new)
│   └── ...
```

#### Core API

**`create_crud_router()` - Main Entry Point:**

```python
from deebase.api import create_crud_router

router = create_crud_router(
    db: Database,                      # DeeBase database instance
    model_cls: type,                   # @dataclass model class
    table_name: str = None,            # Override table name (default: cls.__name__.lower())
    prefix: str = "",                  # URL prefix (e.g., "/api/users")
    tags: list[str] = None,            # OpenAPI tags
    pk_field: str = "id",              # Primary key field name

    # Validation options
    validate_fks: bool = True,         # Check FK references exist before mutations
    validators: dict = None,           # Custom field validators {field: callable}

    # Route customization
    exclude: set[str] = None,          # Exclude routes: {"list", "get", "create", "update", "delete"}
    overrides: dict = None,            # Replace routes: {"create": custom_create_handler}

    # Response options
    response_model_exclude: set = None, # Fields to exclude from responses
)
```

**Usage Example:**

```python
from dataclasses import dataclass
from typing import Optional
from fastapi import FastAPI
from deebase import Database, ForeignKey, Text
from deebase.api import create_crud_router

# Step 1: Define models as dataclasses with inline comments
@dataclass
class User:
    id: int                  # Auto-generated user ID
    name: str                # Display name
    email: str               # Email address (unique)
    status: str = "active"   # Account status: active, inactive, banned

@dataclass
class Post:
    id: int                            # Auto-generated post ID
    author_id: ForeignKey[int, "user"] # Post author (must exist in users)
    title: str                         # Post title, max 200 characters
    content: Text                      # Full post content in markdown
    published: bool = False            # Whether post is publicly visible
    views: int = 0                     # View counter

# Step 2: Create FastAPI app and database
app = FastAPI(title="Blog API")
db = Database("sqlite+aiosqlite:///blog.db")

# Step 3: Startup - create tables
@app.on_event("startup")
async def startup():
    await db.create(User, pk='id', if_not_exists=True)
    await db.create(Post, pk='id', if_not_exists=True)
    await db.enable_foreign_keys()

# Step 4: Add CRUD routers
app.include_router(
    create_crud_router(
        db=db,
        model_cls=User,
        prefix="/api/users",
        tags=["Users"],
    )
)

app.include_router(
    create_crud_router(
        db=db,
        model_cls=Post,
        prefix="/api/posts",
        tags=["Posts"],
        validate_fks=True,  # Validates author_id exists before insert
        validators={
            "title": lambda v: v.strip()[:200] if v else v,  # Trim and limit
        },
    )
)
```

**Generated Endpoints:**

| Method | Path | Request Body | Response | Description |
|--------|------|--------------|----------|-------------|
| GET | `/api/posts/` | - | `list[PostResponse]` | List all posts |
| GET | `/api/posts/{id}` | - | `PostResponse` | Get post by ID |
| POST | `/api/posts/` | `PostCreate` | `PostResponse` | Create post |
| PATCH | `/api/posts/{id}` | `PostUpdate` | `PostResponse` | Update post |
| DELETE | `/api/posts/{id}` | - | 204 No Content | Delete post |

**Generated Pydantic Models:**

```python
# Auto-generated from Post dataclass:

class PostCreate(BaseModel):
    """Request model for creating a Post."""
    author_id: int = Field(..., description="Post author (must exist in users) (FK → user.id)")
    title: str = Field(..., description="Post title, max 200 characters")
    content: str = Field(..., description="Full post content in markdown")
    published: bool = Field(default=False, description="Whether post is publicly visible")
    views: int = Field(default=0, description="View counter")

class PostUpdate(BaseModel):
    """Request model for updating a Post."""
    author_id: Optional[int] = Field(None, description="Post author (FK → user.id)")
    title: Optional[str] = Field(None, description="Post title, max 200 characters")
    # ... all fields optional

class PostResponse(BaseModel):
    """Response model for Post."""
    id: int = Field(..., description="Auto-generated post ID")
    author_id: int = Field(..., description="Post author (FK → user.id)")
    # ... all fields included
```

#### Route Override Mechanism

**Option 1: Using `overrides` parameter:**

```python
async def custom_create_post(data: PostCreate, db=Depends(get_db)):
    # Custom validation
    if "spam" in data.title.lower():
        raise HTTPException(400, "Spam detected")

    table = db.t.post
    result = await table.insert(data.model_dump())
    await send_notification(f"New post: {result['title']}")
    return result

app.include_router(
    create_crud_router(
        db=db,
        model_cls=Post,
        prefix="/api/posts",
        overrides={"create": custom_create_post},
    )
)
```

**Option 2: Exclude and add manually:**

```python
router = create_crud_router(
    db=db,
    model_cls=Post,
    prefix="/api/posts",
    exclude={"create"},  # Don't generate POST endpoint
)

@router.post("/", response_model=PostResponse)
async def create_post(data: PostCreate):
    # Full custom implementation
    ...

app.include_router(router)
```

**Option 3: CRUDRouter subclass with hooks:**

```python
from deebase.api import CRUDRouter

class CustomPostRouter(CRUDRouter):
    """Customized CRUD router for posts."""

    async def before_create(self, data: dict) -> dict:
        """Hook called before insert."""
        data["created_at"] = datetime.now().isoformat()
        return data

    async def after_create(self, record: dict) -> dict:
        """Hook called after insert."""
        await send_notification(f"New post: {record['title']}")
        return record

router = CustomPostRouter(db, Post, prefix="/api/posts")
app.include_router(router.router)
```

#### FK Validation

```python
# When validate_fks=True (default), before insert/update:

async def validate_foreign_keys(db: Database, table: Table, data: dict) -> None:
    """Validate all FK references exist."""
    errors = []

    for fk in table.foreign_keys:
        # fk = {'column': 'author_id', 'references': 'user.id'}
        column = fk['column']
        if column not in data or data[column] is None:
            continue  # Skip null/missing FKs

        ref_table, ref_col = fk['references'].split('.')
        fk_value = data[column]

        try:
            await db.t[ref_table][fk_value]
        except NotFoundError:
            errors.append({
                "field": column,
                "value": fk_value,
                "message": f"Referenced {ref_table} with {ref_col}={fk_value} does not exist"
            })

    if errors:
        raise ForeignKeyValidationError(errors)
```

**Error Response:**

```json
// POST /api/posts/ with {"author_id": 999, "title": "Hello"}
// Returns 422:
{
    "detail": {
        "type": "foreign_key_validation_error",
        "errors": [
            {
                "field": "author_id",
                "value": 999,
                "message": "Referenced user with id=999 does not exist"
            }
        ]
    }
}
```

#### Exception → HTTP Mapping

```python
EXCEPTION_STATUS_MAP = {
    NotFoundError: 404,
    IntegrityError: 422,
    ValidationError: 422,
    ForeignKeyValidationError: 422,
    SchemaError: 500,
    ConnectionError: 503,
    InvalidOperationError: 400,
}
```

#### CLI Commands

**`deebase api init`** - Initialize API with dependency installation:

```bash
$ deebase api init

Installing API dependencies...
  ✓ Dependencies installed via uv

Created:
  api/
    __init__.py
    app.py              # FastAPI application
    routers/__init__.py # Router registration (auto-generated)
    dependencies.py     # Database dependency

Next steps:
  1. Run: deebase api generate --all  (generates and wires routers)
  2. Run: deebase api serve
  Or for admin-only: deebase api serve --admin
```

**`deebase api serve`** - Start development server:

```bash
$ deebase api serve
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     API docs at http://127.0.0.1:8000/docs

$ deebase api serve --host 0.0.0.0 --port 5000 --reload
$ deebase api serve --admin  # Enable admin interface
```

**`deebase api generate`** - Generate router code (auto-detects models):

```bash
$ deebase api generate --all
Found models: User, Post, Comment
Generated: api/routers/users.py (full CRUD with User)
Generated: api/routers/posts.py (full CRUD with Post)
Generated: api/routers/comments.py (full CRUD with Comment)
Updated: api/routers/__init__.py

Full CRUD routers: 3 tables
Run 'deebase api serve' to start the server.
```

**Seamless workflow** - `table create` generates models, `api generate` detects them:

```bash
deebase init
deebase table create users id:int name:str email:str --pk id  # Creates table + model
deebase api init
deebase api generate --all  # Detects User model, generates full CRUD
deebase api serve           # Full REST API ready!
```

#### Testing Without a Webserver

FastAPI's `TestClient` uses HTTPX to make requests directly to the ASGI application in-process, without starting an HTTP server:

```python
from fastapi.testclient import TestClient

@pytest.fixture
def client(app):
    """Create test client - NO SERVER STARTED!"""
    with TestClient(app) as client:
        yield client

def test_create_user(client):
    """POST /api/users/ creates a user."""
    response = client.post("/api/users/", json={
        "name": "Alice",
        "email": "alice@example.com"
    })

    assert response.status_code == 201
    assert response.json()["name"] == "Alice"
```

**How it works:**
1. TestClient wraps the FastAPI app
2. Requests go directly to `app(scope, receive, send)` - no network
3. Response captured from ASGI `send()` calls
4. Fast, isolated, no socket overhead

#### Tests (~55 new tests)

**Router Generation (10):**
- Generate router from dataclass
- Generate Pydantic models with correct types
- Field descriptions from docments
- FK fields annotated in description
- pk_field excluded from Create/Update
- Defaults preserved
- All Optional in Update model
- Handles Text, Optional, datetime types

**Endpoint Tests (12):**
- GET / returns list
- GET / with limit parameter
- GET /{pk} returns single
- GET /{pk} returns 404 for missing
- POST / creates and returns 201
- POST / validates required fields
- PATCH /{pk} updates
- PATCH /{pk} partial update
- PATCH /{pk} returns 404
- DELETE /{pk} returns 204
- DELETE /{pk} returns 404

**FK Validation Tests (8):**
- FK validation passes for valid FK
- FK validation fails for invalid FK
- FK validation skips null FK
- FK validation returns all errors
- FK validation disabled flag
- Multiple FK columns validated
- FK validation on update

**Custom Validators Tests (5):**
- Validator applied on create
- Validator applied on update
- Validator transforms values
- Validator can raise ValidationError
- Multiple validators

**Route Override Tests (8):**
- Override each handler type
- Exclude routes
- Multiple overrides
- Override with custom response model

**CRUDRouter Hooks Tests (6):**
- before_create/after_create
- before_update/after_update
- before_delete/after_delete

**Exception Mapping Tests (4):**
- NotFoundError → 404
- IntegrityError → 422
- ValidationError → 422
- ForeignKeyValidationError → 422

**CLI Tests (4):**
- `deebase api init` creates structure and installs deps
- `deebase api generate` creates router
- `deebase api serve` starts uvicorn

#### Deliverables

**Code:**
- `src/deebase/api/` package (~500 lines)
  - `__init__.py` - Public exports
  - `router.py` - CRUDRouter class and create_crud_router()
  - `models.py` - Pydantic model generation from dataclass + docments
  - `validators.py` - FK validation, custom validators
  - `exceptions.py` - ForeignKeyValidationError
  - `docs.py` - docments integration
- `src/deebase/cli/api_cmd.py` - CLI commands with dependency installation

**Examples:**
- `examples/phase15_fastapi.py` - Basic API example
- `examples/complete_blog_api_example.py` - Full blog with API + HTML routes + custom hooks

**Tests:**
- `tests/test_api_*.py` (~55 tests using TestClient)

**Documentation:**
- `docs/api_reference.md` - Updated with API module
- `docs/cli_reference.md` - New `api` commands
- `docs/implemented.md` - Phase 15 section added
- `docs/best-practices.md` - FastAPI Integration section added
- `docs/how-it-works.md` - FastAPI Architecture section added
- `docs/types_reference.md` - API Types (Pydantic) section added
- `README.md` - Updated with FastAPI examples

#### What's NOT Included

- **Authentication/Authorization** - Use FastAPI's standard patterns
- **Rate limiting** - Use middleware like slowapi
- **Pagination cursors** - Basic limit/offset only
- **Bulk operations** - POST /bulk, DELETE /bulk
- **Filtering/sorting query params** - Use xtra() manually
- **Relationship expansion** - Use views for JOINs
- **GraphQL** - REST only

---

### Phase 16: Data Management & Admin Interface

**Status:** Complete

**Goal:** Add comprehensive data management capabilities through CLI commands and a Django-like admin web interface. Both share a unified validation layer, ensuring consistency between terminal and web operations.

**Completed Deliverables:**
- `src/deebase/validation.py` - Shared validation layer (apply_validators, validate_foreign_keys, ValidatedTable)
- `src/deebase/cli/data_cmd.py` - CLI data commands (insert, list, get, update, delete)
- `src/deebase/admin/` - Django-like admin interface with templates
- Updated `deebase init` to create validators/ directory
- Updated `api serve --admin` flag to enable admin interface
- `ForeignKeyValidationError` moved to main exceptions.py
- 24 new validation tests + 55 CLI command tests (494 total passing tests)
- `examples/phase16_data_admin.py` - Phase 16 example

#### Design Principles

1. **Validation is opt-in** - Core Table class stays simple; validation is application-layer
2. **Shared validators** - CLI and API use the same validator functions from project's `validators/` directory
3. **Independence** - CLI data commands work without FastAPI installed
4. **Feature parity** - Whatever CLI can do, admin UI can do

#### Architecture Overview

```
                    ┌─────────────────────┐
                    │  validators/        │  ← Project-specific
                    │  (user-defined)     │     validator functions
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
    ┌─────────────────┐ ┌─────────────┐ ┌─────────────┐
    │ deebase data    │ │ API routes  │ │ Admin UI    │
    │ (CLI commands)  │ │ (FastAPI)   │ │ (forms)     │
    └────────┬────────┘ └──────┬──────┘ └──────┬──────┘
             │                 │               │
             └────────────────┬┴───────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │ deebase.validation  │  ← Shared validation
                    │ - apply_validators  │     engine (in library)
                    │ - validate_fks      │
                    │ - ValidatedTable    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ deebase.Table       │  ← Core CRUD
                    │ (no validation)     │     (DB handles constraints)
                    └─────────────────────┘
```

#### Part 1: Shared Validation Layer

**Goal:** Extract validation utilities so CLI, API, and admin can share them.

**New file: `src/deebase/validation.py`**

```python
"""Shared validation utilities for DeeBase.

Used by CLI (deebase data), API (create_crud_router), and admin UI.
The core Table class does NOT use these automatically - they are opt-in.
"""

from deebase.exceptions import ForeignKeyValidationError, ValidationError


def apply_validators(data: dict, validators: dict) -> dict:
    """Apply field validators to data.

    Args:
        data: Record data dict
        validators: Dict of field_name → validator_function

    Returns:
        Validated (possibly transformed) data

    Raises:
        ValidationError: If any validator fails
    """
    errors = []
    result = data.copy()

    for field, validator in validators.items():
        if field in result and result[field] is not None:
            try:
                result[field] = validator(result[field])
            except (ValueError, TypeError) as e:
                errors.append({"field": field, "message": str(e)})

    if errors:
        raise ValidationError("Validation failed", errors=errors)

    return result


async def validate_foreign_keys(db, table, data: dict) -> None:
    """Validate FK references exist.

    Args:
        db: Database instance
        table: Table to validate against
        data: Record data to validate

    Raises:
        ForeignKeyValidationError: If any FK references don't exist
    """
    errors = []

    for fk in table.foreign_keys:
        column = fk['column']
        if column not in data or data[column] is None:
            continue

        ref_table, ref_col = fk['references'].split('.')
        fk_value = data[column]

        try:
            parent_table = db._get_table(ref_table)
            await parent_table[fk_value]
        except Exception:
            errors.append({
                "field": column,
                "value": fk_value,
                "message": f"Referenced {ref_table} with {ref_col}={fk_value} does not exist"
            })

    if errors:
        raise ForeignKeyValidationError(errors)


class ValidatedTable:
    """Wrapper that adds validation to Table write operations.

    All read operations pass through unchanged. Write operations
    (insert, update, upsert) validate before delegating to the
    underlying table.

    Example:
        vusers = ValidatedTable(users, validators=USER_VALIDATORS)
        await vusers.insert(data)  # Validates → inserts → returns dataclass

        # Original table unchanged
        await users.insert(data)  # No validation
    """

    def __init__(self, table, validators: dict = None, validate_fks: bool = True):
        self._table = table
        self._validators = validators or {}
        self._validate_fks = validate_fks

    # === Write operations (with validation) ===

    async def insert(self, data):
        validated = await self._validate(data)
        return await self._table.insert(validated)

    async def update(self, data):
        validated = await self._validate(data)
        return await self._table.update(validated)

    async def upsert(self, data):
        validated = await self._validate(data)
        return await self._table.upsert(validated)

    async def delete(self, pk):
        return await self._table.delete(pk)  # No validation needed

    # === Read operations (passthrough) ===

    async def __call__(self, limit=None, offset=None, with_pk=False):
        return await self._table(limit=limit, offset=offset, with_pk=with_pk)

    async def __getitem__(self, pk):
        return await self._table[pk]

    async def lookup(self, **kwargs):
        return await self._table.lookup(**kwargs)

    # === Properties (passthrough) ===

    @property
    def schema(self):
        return self._table.schema

    @property
    def foreign_keys(self):
        return self._table.foreign_keys

    @property
    def indexes(self):
        return self._table.indexes

    @property
    def fk(self):
        return self._table.fk

    @property
    def name(self):
        return self._table.name

    # === Methods that return Tables (re-wrap) ===

    def xtra(self, **kwargs):
        new_table = self._table.xtra(**kwargs)
        return ValidatedTable(new_table, self._validators, self._validate_fks)

    # === Dataclass support ===

    def dataclass(self):
        return self._table.dataclass()

    # === Internal ===

    async def _validate(self, data: dict) -> dict:
        from deebase.dataclass_utils import record_to_dict
        data_dict = record_to_dict(data)
        validated = apply_validators(data_dict, self._validators)
        if self._validate_fks:
            await validate_foreign_keys(self._table._db, self._table, validated)
        return validated
```

**Refactor `src/deebase/api/validators.py`:**

```python
# Backward compatibility re-exports
from deebase.validation import apply_validators, validate_foreign_keys
from deebase.exceptions import ForeignKeyValidationError

# Keep API-specific validators here if any
```

**Move `ForeignKeyValidationError` to `src/deebase/exceptions.py`:**

```python
class ForeignKeyValidationError(DeeBaseError):
    """Raised when FK references don't exist during validation."""

    def __init__(self, errors: list[dict]):
        self.errors = errors
        msg = "; ".join(e["message"] for e in errors)
        super().__init__(msg)

    def to_dict(self) -> dict:
        return {"type": "foreign_key_validation_error", "errors": self.errors}
```

#### Part 2: Project Validators Directory

**Created by `deebase init`:**

```
project/
├── .deebase/
│   ├── config.toml
│   └── state.json
├── validators/              # NEW: Shared validators
│   ├── __init__.py          # Registry of all validators
│   └── example.py           # Template to copy
├── api/
├── models/
└── data/
```

**validators/__init__.py:**

```python
"""Validator registry for all tables.

Used by both CLI (deebase data) and API routes.

To add validators for a table:
1. Create a file: validators/your_table.py
2. Define validator functions and VALIDATORS dict
3. Import and register here

Example:
    from . import users

    VALIDATORS = {
        "users": users.VALIDATORS,
    }
"""

# Table name → validators dict
VALIDATORS: dict[str, dict] = {}


def get_validators(table_name: str) -> dict:
    """Get validators for a table."""
    return VALIDATORS.get(table_name, {})
```

**validators/example.py (template):**

```python
"""Example validators - copy this file for your tables.

Validators are plain functions that:
- Receive a field value
- Return the (possibly transformed) value
- Raise ValueError with message on invalid input

These validators are used by BOTH:
- CLI: deebase data insert/update
- API: create_crud_router(validators=...)
- Admin: Web forms
"""
import re


def validate_email(value: str) -> str:
    """Validate and normalize email format."""
    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", value):
        raise ValueError("Invalid email format")
    return value.lower()  # Normalize


def validate_non_empty(value: str) -> str:
    """Ensure string is not empty or whitespace."""
    if not value or not value.strip():
        raise ValueError("Cannot be empty")
    return value.strip()


# Register validators for this table
VALIDATORS = {
    # "email": validate_email,
    # "name": validate_non_empty,
}
```

#### Part 3: CLI Data Commands

**New file: `src/deebase/cli/data_cmd.py`**

```bash
# Insert record
$ deebase data insert users --name "Alice" --email "alice@example.com"
Created user with id: 1

# Insert with FK (validates existence)
$ deebase data insert posts --title "Hello" --author_id 1
Created post with id: 1

# Insert with invalid FK
$ deebase data insert posts --title "Bad" --author_id 999
Error: Foreign key violation: author_id=999 references user.id which does not exist

# List records
$ deebase data list users
┌────┬───────┬───────────────────┬────────┐
│ id │ name  │ email             │ status │
├────┼───────┼───────────────────┼────────┤
│  1 │ Alice │ alice@example.com │ active │
│  2 │ Bob   │ bob@example.com   │ active │
└────┴───────┴───────────────────┴────────┘

$ deebase data list users --limit 10 --format json
$ deebase data list users --format csv

# Get single record
$ deebase data get users 1
{
  "id": 1,
  "name": "Alice",
  "email": "alice@example.com"
}

# Update record
$ deebase data update users 1 --status inactive
Updated user 1

# Delete record
$ deebase data delete users 1
Delete user 1? [y/N]: y
Deleted user 1

$ deebase data delete users 1 -y  # Skip confirmation

# Batch insert from JSON file
$ deebase data insert users --from-file users.json
Inserted 10 records into users

# Interactive mode for FK fields
$ deebase data insert posts --title "Hello" --interactive
Select author_id:
  1. Alice (id: 1)
  2. Bob (id: 2)
  3. Charlie (id: 3)
> 1
Created post with id: 1
```

**Implementation:**

```python
@click.group()
def data():
    """Data management commands."""
    pass


@data.command('insert')
@click.argument('table')
@click.option('--from-file', type=click.Path(exists=True), help='JSON file with records')
@click.option('--interactive', '-i', is_flag=True, help='Interactive mode for FK fields')
@click.option('--field', '-f', multiple=True, help='Field values as field=value')
@click.pass_context
def data_insert(ctx, table, from_file, interactive, field):
    """Insert records into a table."""
    run_async(_data_insert(table, from_file, interactive, field))


@data.command('list')
@click.argument('table')
@click.option('--limit', '-l', type=int, default=100, help='Max records to show')
@click.option('--offset', '-o', type=int, default=0, help='Skip N records')
@click.option('--format', '-f', type=click.Choice(['table', 'json', 'csv']), default='table')
def data_list(table, limit, offset, format):
    """List records from a table."""
    run_async(_data_list(table, limit, offset, format))


@data.command('get')
@click.argument('table')
@click.argument('pk')
@click.option('--format', '-f', type=click.Choice(['json', 'table']), default='json')
def data_get(table, pk, format):
    """Get a single record by primary key."""
    run_async(_data_get(table, pk, format))


@data.command('update')
@click.argument('table')
@click.argument('pk')
@click.option('--field', '-f', multiple=True, help='Field values as field=value')
def data_update(table, pk, field):
    """Update a record."""
    run_async(_data_update(table, pk, field))


@data.command('delete')
@click.argument('table')
@click.argument('pk')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation')
def data_delete(table, pk, yes):
    """Delete a record."""
    run_async(_data_delete(table, pk, yes))
```

**Internal implementation:**

```python
async def _data_insert(table_name: str, from_file: str, interactive: bool, fields: tuple):
    ensure_initialized()
    config = load_config()
    load_env()

    db = Database(config.get_database_url())

    try:
        # Check table exists
        await db.reflect_table(table_name)
        table = db.t[table_name]
    except Exception:
        click.echo(f"Error: Table '{table_name}' not found", err=True)
        return

    # Load validators from project
    validators = load_project_validators(table_name)

    if from_file:
        # Batch insert from JSON file
        import json
        with open(from_file) as f:
            records = json.load(f)

        count = 0
        for record in records:
            validated = apply_validators(record, validators)
            await validate_foreign_keys(db, table, validated)
            await table.insert(validated)
            count += 1

        click.echo(f"Inserted {count} records into {table_name}")
    else:
        # Single record from --field options
        data = parse_field_values(fields)

        if interactive:
            data = await interactive_fk_selection(db, table, data)

        # Validate
        validated = apply_validators(data, validators)
        await validate_foreign_keys(db, table, validated)

        # Insert
        record = await table.insert(validated)
        pk_col = list(table.sa_table.primary_key.columns)[0].name
        click.echo(f"Created {table_name} with {pk_col}: {record[pk_col]}")

    await db.close()


def load_project_validators(table_name: str) -> dict:
    """Load validators from project's validators/ directory."""
    validators_dir = Path.cwd() / "validators"
    if not validators_dir.exists():
        return {}

    try:
        # Try to import validators module
        sys.path.insert(0, str(Path.cwd()))
        from validators import get_validators
        return get_validators(table_name)
    except ImportError:
        return {}
    finally:
        if str(Path.cwd()) in sys.path:
            sys.path.remove(str(Path.cwd()))
```

#### Part 4: Admin Web Interface

**Enabled with `--admin` flag:**

```bash
$ deebase api serve --admin
INFO:     Admin interface enabled at /admin/
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     API docs at http://127.0.0.1:8000/docs
```

**Routes:**

| Route | Method | Description |
|-------|--------|-------------|
| `/admin/` | GET | Dashboard: list of all tables |
| `/admin/{table}/` | GET | List view with pagination |
| `/admin/{table}/new` | GET | Create form |
| `/admin/{table}/new` | POST | Submit create |
| `/admin/{table}/{pk}` | GET | Detail/edit form |
| `/admin/{table}/{pk}` | POST | Submit update |
| `/admin/{table}/{pk}/delete` | GET | Delete confirmation |
| `/admin/{table}/{pk}/delete` | POST | Confirm delete |

**New package: `src/deebase/admin/`**

```
src/deebase/admin/
├── __init__.py           # create_admin_router()
├── router.py             # Admin FastAPI routes
├── templates/
│   ├── base.html         # Base layout
│   ├── dashboard.html    # Table list
│   ├── list.html         # Record list with pagination
│   ├── detail.html       # View/edit form
│   ├── create.html       # Create form
│   └── delete.html       # Delete confirmation
└── static/
    └── admin.css         # Minimal styling (Pico CSS or custom)
```

**Admin Router Implementation:**

```python
from fastapi import APIRouter, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from pathlib import Path

def create_admin_router(db: "Database") -> APIRouter:
    """Create admin interface router.

    Args:
        db: Database instance with reflected tables

    Returns:
        FastAPI router mounted at /admin/
    """
    router = APIRouter(prefix="/admin", tags=["Admin"])
    templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

    @router.get("/")
    async def admin_dashboard(request: Request):
        """Show list of all tables."""
        tables = list(db._tables.keys())
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "tables": tables,
        })

    @router.get("/{table_name}/")
    async def admin_list(request: Request, table_name: str, page: int = 1, per_page: int = 25):
        """List records in a table with pagination."""
        table = db._get_table(table_name)
        offset = (page - 1) * per_page
        records = await table(limit=per_page, offset=offset)

        # Get column names for header
        columns = [c.name for c in table.sa_table.columns]
        pk_col = list(table.sa_table.primary_key.columns)[0].name

        return templates.TemplateResponse("list.html", {
            "request": request,
            "table_name": table_name,
            "columns": columns,
            "pk_col": pk_col,
            "records": records,
            "page": page,
            "per_page": per_page,
        })

    @router.get("/{table_name}/new")
    async def admin_create_form(request: Request, table_name: str):
        """Show create form."""
        table = db._get_table(table_name)
        columns = [c for c in table.sa_table.columns if c.name not in table.sa_table.primary_key.columns.keys()]

        # Get FK options for dropdown fields
        fk_options = await _get_fk_options(db, table)

        return templates.TemplateResponse("create.html", {
            "request": request,
            "table_name": table_name,
            "columns": columns,
            "fk_options": fk_options,
        })

    @router.post("/{table_name}/new")
    async def admin_create_submit(request: Request, table_name: str):
        """Handle create form submission."""
        table = db._get_table(table_name)
        form_data = await request.form()
        data = dict(form_data)

        # Load and apply validators
        validators = load_project_validators(table_name)
        validated = apply_validators(data, validators)
        await validate_foreign_keys(db, table, validated)

        record = await table.insert(validated)
        pk_col = list(table.sa_table.primary_key.columns)[0].name

        return RedirectResponse(
            url=f"/admin/{table_name}/{record[pk_col]}",
            status_code=303
        )

    # ... similar for detail, update, delete

    return router


async def _get_fk_options(db, table) -> dict:
    """Get options for FK dropdown fields."""
    fk_options = {}

    for fk in table.foreign_keys:
        column = fk['column']
        ref_table_name, ref_col = fk['references'].split('.')

        try:
            ref_table = db._get_table(ref_table_name)
            records = await ref_table(limit=100)

            # Try to find a display field (name, title, etc.)
            display_field = None
            for col in ['name', 'title', 'label', 'email', 'username']:
                if col in records[0] if records else []:
                    display_field = col
                    break

            fk_options[column] = [
                {
                    "value": r[ref_col],
                    "label": f"{r.get(display_field, '')} (id: {r[ref_col]})" if display_field else str(r[ref_col])
                }
                for r in records
            ]
        except Exception:
            fk_options[column] = []

    return fk_options
```

**Integration with `api serve`:**

```python
# In api_cmd.py

@api.command('serve')
@click.option('--host', default='127.0.0.1', help='Host to bind to')
@click.option('--port', default=8000, type=int, help='Port to bind to')
@click.option('--reload', is_flag=True, help='Enable auto-reload')
@click.option('--admin', is_flag=True, help='Enable admin interface at /admin/')
def api_serve(host: str, port: int, reload: bool, admin: bool):
    """Start the FastAPI development server."""
    ensure_initialized()
    load_env()

    if admin:
        click.echo("Admin interface enabled at /admin/")
        # Set environment variable for app.py to detect
        os.environ['DEEBASE_ADMIN_ENABLED'] = '1'

    # Start uvicorn
    cmd = [
        sys.executable, "-m", "uvicorn",
        "api.app:app",
        "--host", host,
        "--port", str(port),
    ]
    if reload:
        cmd.append("--reload")

    subprocess.run(cmd)
```

**Template Example (list.html):**

{% raw %}
```html
{% extends "base.html" %}

{% block content %}
<div class="admin-container">
    <header>
        <h1>{{ table_name }}</h1>
        <a href="/admin/{{ table_name }}/new" class="button">+ Add {{ table_name }}</a>
    </header>

    <table>
        <thead>
            <tr>
                {% for col in columns %}
                <th>{{ col }}</th>
                {% endfor %}
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for record in records %}
            <tr>
                {% for col in columns %}
                <td>{{ record[col] }}</td>
                {% endfor %}
                <td>
                    <a href="/admin/{{ table_name }}/{{ record[pk_col] }}">Edit</a>
                    <a href="/admin/{{ table_name }}/{{ record[pk_col] }}/delete" class="danger">Delete</a>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>

    <nav class="pagination">
        {% if page > 1 %}
        <a href="?page={{ page - 1 }}">← Previous</a>
        {% endif %}
        <span>Page {{ page }}</span>
        {% if records|length == per_page %}
        <a href="?page={{ page + 1 }}">Next →</a>
        {% endif %}
    </nav>
</div>
{% endblock %}
```
{% endraw %}

#### Part 5: Update `deebase init`

**Modified `init_cmd.py`:**

```python
@click.command('init')
@click.option('--package', help='Existing Python package to integrate with')
@click.option('--new-package', help='Create new Python package')
@click.option('--postgres', is_flag=True, help='Use PostgreSQL instead of SQLite')
def init(package: str, new_package: str, postgres: bool):
    """Initialize a new DeeBase project."""
    # ... existing code ...

    # Create validators directory (NEW)
    validators_dir = Path("validators")
    validators_dir.mkdir(exist_ok=True)

    # Create __init__.py
    (validators_dir / "__init__.py").write_text('''"""Validator registry for all tables.

Used by both CLI (deebase data) and API routes.
See validators/example.py for how to create validators.
"""

# Table name → validators dict
VALIDATORS: dict[str, dict] = {}


def get_validators(table_name: str) -> dict:
    """Get validators for a table."""
    return VALIDATORS.get(table_name, {})
''')

    # Create example.py template
    (validators_dir / "example.py").write_text('''"""Example validators - copy this file for your tables.

Validators are plain functions that:
- Receive a field value
- Return the (possibly transformed) value
- Raise ValueError with message on invalid input

These validators are used by BOTH:
- CLI: deebase data insert/update
- API: create_crud_router(validators=...)
- Admin: Web forms
"""
import re


def validate_email(value: str) -> str:
    """Validate and normalize email format."""
    if not re.match(r"^[^@]+@[^@]+\\.[^@]+$", value):
        raise ValueError("Invalid email format")
    return value.lower()


def validate_non_empty(value: str) -> str:
    """Ensure string is not empty or whitespace."""
    if not value or not value.strip():
        raise ValueError("Cannot be empty")
    return value.strip()


# Register validators for this table
VALIDATORS = {
    # "email": validate_email,
    # "name": validate_non_empty,
}
''')

    click.echo("Created validators/ directory with example validators")
    # ... rest of init ...
```

#### Tests (~50 new tests)

**Validation Layer (12 tests):**
- `apply_validators()` transforms values
- `apply_validators()` raises ValidationError on failure
- `apply_validators()` skips None values
- `validate_foreign_keys()` passes for valid FKs
- `validate_foreign_keys()` fails for invalid FKs
- `validate_foreign_keys()` skips null FKs
- `ValidatedTable.insert()` validates before insert
- `ValidatedTable.update()` validates before update
- `ValidatedTable` preserves dataclass behavior
- `ValidatedTable.xtra()` re-wraps with validators
- Backward compatibility with api/validators.py imports

**CLI Data Commands (18 tests):**
- `deebase data list` shows records in table format
- `deebase data list --format json` outputs JSON
- `deebase data list --format csv` outputs CSV
- `deebase data list --limit N` limits results
- `deebase data get` returns single record
- `deebase data get` returns 404 for missing
- `deebase data insert` creates record
- `deebase data insert` validates fields
- `deebase data insert` validates FK references
- `deebase data insert --from-file` batch imports
- `deebase data update` modifies record
- `deebase data update` validates fields
- `deebase data delete` removes record
- `deebase data delete -y` skips confirmation
- Table existence check before operations
- Loads validators from project directory

**Admin Interface (20 tests):**
- Dashboard lists all tables
- List view shows records
- List view pagination works
- Create form shows columns
- Create form shows FK dropdowns
- Create submit validates
- Create submit validates FKs
- Create redirects to detail
- Detail view shows record
- Update form pre-fills values
- Update submit validates
- Delete confirmation page
- Delete removes record
- `--admin` flag enables routes
- Admin disabled without flag
- Templates render correctly
- FK dropdown populated from parent table
- Error messages shown on validation failure

#### Deliverables

**Code:**
- `src/deebase/validation.py` (~150 lines) - Shared validation layer
- `src/deebase/cli/data_cmd.py` (~300 lines) - CLI data commands
- `src/deebase/admin/` package (~400 lines) - Admin interface
- Updated `src/deebase/cli/init_cmd.py` - Create validators/
- Updated `src/deebase/cli/api_cmd.py` - `--admin` flag
- Updated `src/deebase/exceptions.py` - Move ForeignKeyValidationError
- Updated `src/deebase/api/validators.py` - Re-export from validation.py

**Templates:**
- `admin/templates/base.html`
- `admin/templates/dashboard.html`
- `admin/templates/list.html`
- `admin/templates/create.html`
- `admin/templates/detail.html`
- `admin/templates/delete.html`
- `admin/static/admin.css`

**Examples:**
- `examples/phase16_data_admin.py` - CLI data commands and admin usage

**Tests:**
- `tests/test_validation.py` - Validation layer tests
- `tests/test_cli_data.py` - CLI data command tests
- `tests/test_admin.py` - Admin interface tests (TestClient)

**Documentation:**
- `docs/api_reference.md` - Add validation module, ValidatedTable
- `docs/cli_reference.md` - Add `data` commands, `--admin` flag
- `docs/fastapi_guide.md` - Admin interface section
- `docs/implemented.md` - Phase 16 section
- `docs/best-practices.md` - Validation patterns section
- `README.md` - Update for Phase 16

#### What We're NOT Implementing

- **Authentication for admin** - User's responsibility (middleware)
- **Role-based permissions** - Too complex, use custom logic
- **Inline editing in list view** - Keep it simple
- **File uploads** - Not part of core CRUD
- **Custom admin actions** - Subclass CRUDRouter if needed
- **Audit logging** - Use hooks in CRUDRouter
- **Search/filter in admin** - Use views for complex queries

#### Dependencies (Updated)

```toml
[project.optional-dependencies]
api = [
    "fastapi>=0.100.0",
    "pydantic>=2.0",
    "fastcore>=1.5.0",
    "uvicorn>=0.20.0",
    "jinja2>=3.0",      # Already included, for admin templates
]
```

No new dependencies required - Jinja2 is already in the `[api]` extra.

---

### Phase 17: Admin UI Enhancements

**Status:** Ongoing

**Goal:** Improve admin interface with read-only detail views, clickable rows, and customizable field rendering.

**Planned Deliverables:**
- Read-only detail view at `/{table}/{pk}` (edit moves to `/{table}/{pk}/edit`)
- Clickable rows in list view navigate to detail view
- Type-based field renderers (JSON as `<pre>`, TEXT in styled div, etc.)
- Custom display functions via `displays/` directory (auto-discovery)
- `deebase init` creates `displays/` scaffold
- Updated screenshots and documentation
- Tests for new routes and renderers

#### URL Structure Changes

| Before | After | Purpose |
|--------|-------|---------|
| `/{table}/{pk}` | `/{table}/{pk}` | **Read-only view** (NEW) |
| `/{table}/{pk}` | `/{table}/{pk}/edit` | Edit form (MOVED) |
| `/{table}/{pk}/delete` | `/{table}/{pk}/delete` | Delete confirm (unchanged) |

#### Part 1: Read-Only Detail View

**Template changes:**
- Rename `detail.html` → `edit.html`
- Create `view.html` - read-only display with Edit/Delete buttons

**Router changes:**
- New route `GET /{table}/{pk}` → renders `view.html`
- Move edit form to `GET /{table}/{pk}/edit`
- Move update handler to `POST /{table}/{pk}/edit`
- Update redirects after create/update to go to view page

**List template changes:**
- Make rows clickable (link to detail view)
- Keep Edit/Delete in Actions column or simplify

#### Part 2: Field Renderers

**New file: `src/deebase/admin/renderers.py`**

```python
"""Field renderers for admin detail view.

Each renderer takes (value, record, col_type) and returns HTML string.
Custom displays can override per table/field.
"""

def render_json(value, record, col_type):
    """Default renderer for JSON/dict types."""
    if value is None:
        return '<span class="null">—</span>'
    import json
    return f'<pre class="json-value">{json.dumps(value, indent=2)}</pre>'

def render_text(value, record, col_type):
    """Default renderer for TEXT columns."""
    if value is None:
        return '<span class="null">—</span>'
    return f'<div class="text-value">{value}</div>'

def render_boolean(value, record, col_type):
    if value is None:
        return '<span class="null">—</span>'
    return "Yes" if value else "No"

def render_default(value, record, col_type):
    if value is None:
        return '<span class="null">—</span>'
    return str(value)

# Type -> renderer mapping
TYPE_RENDERERS = {
    "JSON": render_json,
    "TEXT": render_text,
    "BOOLEAN": render_boolean,
    "BOOL": render_boolean,
}

def get_renderer(col_type: str):
    """Get default renderer for a column type."""
    col_type_upper = col_type.upper()
    for type_key, renderer in TYPE_RENDERERS.items():
        if type_key in col_type_upper:
            return renderer
    return render_default


def render_field(table_name: str, col_name: str, col_type: str, value, record):
    """Render a field value - checks custom displays first, then type default."""
    custom = _load_custom_display(table_name, col_name)
    if custom:
        return custom(value, record)

    renderer = get_renderer(col_type)
    return renderer(value, record, col_type)
```

#### Part 3: Custom Display Functions

**Auto-discovery pattern (like validators):**

```
displays/
  articles.py    # auto-discovered for "articles" table
  users.py       # auto-discovered for "users" table
```

```python
# displays/articles.py
def render_history(value, record):
    """Custom HTML for LLM history JSON field."""
    if not value:
        return "<em>No history</em>"

    html = '<div class="chat-history">'
    for msg in value.get("messages", []):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        html += f'<div class="msg msg-{role}"><strong>{role}:</strong> {content}</div>'
    html += '</div>'
    return html

DISPLAYS = {
    "history": render_history,
}
```

**Loading mechanism:**

```python
def _load_custom_display(table_name: str, field_name: str):
    """Auto-discover displays/{table_name}.py and look up field."""
    import sys
    import importlib
    from pathlib import Path

    displays_dir = Path.cwd() / "displays"
    if not displays_dir.exists():
        return None

    try:
        if str(Path.cwd()) not in sys.path:
            sys.path.insert(0, str(Path.cwd()))

        module = importlib.import_module(f"displays.{table_name}")
        return getattr(module, "DISPLAYS", {}).get(field_name)
    except ImportError:
        return None
```

#### Part 4: Template Updates

**view.html (new):**
{% raw %}
```html
{% extends "base.html" %}

{% block title %}{{ table_name }} #{{ pk }} - DeeBase Admin{% endblock %}

{% block content %}
<div class="breadcrumb">
    <a href="/admin/">Dashboard</a> &gt;
    <a href="/admin/{{ table_name }}/">{{ table_name }}</a> &gt;
    #{{ pk }}
</div>

<div class="page-header">
    <h1>{{ table_name }} #{{ pk }}</h1>
    <div class="actions">
        <a href="/admin/{{ table_name }}/{{ pk }}/edit" class="btn btn-primary">Edit</a>
        <a href="/admin/{{ table_name }}/{{ pk }}/delete" class="btn btn-danger">Delete</a>
    </div>
</div>

<div class="card">
    {% for col in columns %}
    <div class="field-row">
        <label>{{ col.name }}{% if col.is_pk %} (PK){% endif %}</label>
        <div class="field-value">
            {{ render_field(table_name, col.name, col.type, record[col.name], record) | safe }}
        </div>
    </div>
    {% endfor %}
</div>
{% endblock %}
```
{% endraw %}

#### Documentation Updates

1. `examples/phase17_admin_enhancements.py` - Phase example
2. `docs/fastapi_guide.md` - Update Admin URLs table, add screenshots
3. `docs/api_reference.md` - Document renderers API
4. `docs/cli_reference.md` - Update if `deebase init` changes
5. `docs/implemented.md` - Phase 17 section
6. `README.md` - Update admin description
7. `CLAUDE.md` - Mark Phase 17 complete

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
