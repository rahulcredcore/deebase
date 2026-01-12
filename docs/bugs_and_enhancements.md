# Bugs and Enhancements

Tracking known issues and planned improvements.

## Enhancements

### 1. Generated dataclass types don't respect NOT NULL constraints

**Status**: Planned
**Priority**: Low
**Affects**: `deebase codegen`, `table.dataclass()`

**Issue**: Currently, `make_table_dataclass()` makes ALL fields `Optional[T] = None` to handle auto-increment PKs. This is misleading for NOT NULL columns and composite PKs.

**Current behavior**:
```python
# Schema: tenant_id INTEGER NOT NULL, user_id INTEGER NOT NULL, username VARCHAR NOT NULL
# PK: (tenant_id, user_id)

@dataclass
class Users:
    tenant_id: Optional[int] = None  # misleading - actually required
    user_id: Optional[int] = None    # misleading - actually required
    username: Optional[str] = None   # misleading - actually required
```

**Desired behavior**:
```python
@dataclass(kw_only=True)
class Users:
    tenant_id: int      # required - composite PK
    user_id: int        # required - composite PK
    username: str       # required - NOT NULL
```

**Detection logic**:
1. Composite PK → All PK columns required (never auto-increment)
2. Single integer PK with `autoincrement=True` or `"auto"` → `Optional[int] = None`
3. Nullable column → `Optional[T] = None`
4. Everything else → required (no Optional, no default)

**Implementation**:
- Update `make_table_dataclass()` in `dataclass_utils.py`
- Use `kw_only=True` (Python 3.10+) to avoid field ordering issues
- Update `dataclass_src()` to emit `@dataclass(kw_only=True)`

**Workaround**: The Python code works correctly - only the type hints are misleading. Provide explicit values for all required fields when constructing dataclass instances:

```python
# Generated (misleading types):
@dataclass
class Users:
    tenant_id: Optional[int] = None
    user_id: Optional[int] = None
    username: Optional[str] = None

# Workaround: Just provide explicit values, ignore the Optional hints
user = Users(tenant_id=1, user_id=100, username="alice")
await users.insert(user)

# The insert works fine - the database enforces NOT NULL constraints
```

---

### 2. Composite Foreign Key Support

**Status**: Planned
**Priority**: Medium
**Affects**: `ForeignKey` annotation, `db.create()`, FK validation in API

**Issue**: DeeBase only supports single-column foreign keys. Tables with composite PKs cannot be properly referenced.

**Current limitation**:
```python
# users table has composite PK (tenant_id, user_id)
# hist table wants to FK to users - NOT POSSIBLE with current syntax

@dataclass
class Hist:
    tenant_id: ForeignKey[int, "users.tenant_id"]  # Creates separate FK - WRONG
    user_id: ForeignKey[int, "users.user_id"]      # Creates separate FK - WRONG
    event: str
```

The FK validation would try `users[single_value]` which raises `ValidationError` because `users` expects a composite PK tuple.

**Desired behavior**:
```python
from deebase import CompositeForeignKey

@dataclass
class Hist:
    tenant_id: int
    user_id: int
    event: str

    __composite_fks__ = [
        CompositeForeignKey(
            columns=["tenant_id", "user_id"],
            references="users",
            ref_columns=["tenant_id", "user_id"]
        )
    ]
```

**CLI Syntax**:
```bash
# Arrow syntax with explicit columns
deebase table create hist \
    tenant_id:int \
    user_id:int \
    event:str \
    --pk tenant_id,user_id \
    --cfk "tenant_id,user_id -> users(tenant_id,user_id)"

# Shorthand when column names match
deebase table create hist \
    tenant_id:int \
    user_id:int \
    event:str \
    --pk tenant_id,user_id \
    --cfk "tenant_id,user_id -> users"

# Multiple composite FKs
deebase table create audit \
    tenant_id:int \
    user_id:int \
    target_tenant:int \
    target_user:int \
    action:str \
    --pk id \
    --cfk "tenant_id,user_id -> users" \
    --cfk "target_tenant,target_user -> users(tenant_id,user_id)"
```

**Implementation Strategy**:

| File | Change |
|------|--------|
| `types.py` | Add `CompositeForeignKey` class |
| `table.py` | Update `foreign_keys` property to include composite FKs |
| `database.py` | Handle `__composite_fks__` in `create()`, add `ForeignKeyConstraint` |
| `api/validators.py` | Handle composite FK validation with tuple lookup |
| `api/router.py` | Extract composite FK metadata from `__composite_fks__` |
| `cli/parser.py` | Parse `--cfk` flag syntax |
| `cli/table_cmd.py` | Add `--cfk` option to `table create` |

**Schema creation**:
```python
# In db.create(), after creating columns:
if hasattr(cls, '__composite_fks__'):
    for cfk in cls.__composite_fks__:
        from sqlalchemy import ForeignKeyConstraint
        constraint = ForeignKeyConstraint(
            cfk.columns,
            [f"{cfk.references}.{c}" for c in cfk.ref_columns]
        )
        sa_table.append_constraint(constraint)
```

**FK metadata format**:
```python
# Single FK (existing):
{"column": "author_id", "references": "users.id"}

# Composite FK (new):
{"columns": ["tenant_id", "user_id"], "references": "users", "ref_columns": ["tenant_id", "user_id"]}
```

**Validation logic**:
```python
for fk in table.foreign_keys:
    if "column" in fk:
        # Single FK - existing logic
        await parent_table[fk_value]
    elif "columns" in fk:
        # Composite FK - tuple lookup
        values = [data.get(col) for col in fk["columns"]]
        if None in values:
            continue  # Skip if any column missing
        await parent_table[tuple(values)]  # Uses composite PK lookup
```

**Workaround**: Disable automatic FK validation and implement custom validation in a `before_create` hook:

```python
from deebase.api import CRUDRouter
from fastapi import HTTPException

class HistRouter(CRUDRouter):
    async def before_create(self, data: dict) -> dict:
        # Custom composite FK validation
        result = await users.lookup(
            tenant_id=data["tenant_id"],
            user_id=data["user_id"]
        )
        if not result:
            raise HTTPException(
                status_code=422,
                detail=f"Referenced user ({data['tenant_id']}, {data['user_id']}) does not exist"
            )
        return data

    async def before_update(self, pk: Any, data: dict) -> dict:
        # Same validation for updates if FK columns can change
        if "tenant_id" in data or "user_id" in data:
            # Need full record to validate
            table = await self._get_table()
            existing = await table[pk]
            tenant_id = data.get("tenant_id", existing["tenant_id"])
            user_id = data.get("user_id", existing["user_id"])

            result = await users.lookup(tenant_id=tenant_id, user_id=user_id)
            if not result:
                raise HTTPException(
                    status_code=422,
                    detail=f"Referenced user ({tenant_id}, {user_id}) does not exist"
                )
        return data

# Use with validate_fks=False to disable broken single-column validation
router = HistRouter(
    db,
    Hist,
    prefix="/api/hist",
    validate_fks=False  # IMPORTANT: disable automatic FK validation
)
app.include_router(router.router)
```

For Python API usage (without FastAPI):
```python
# Manual validation before insert
async def insert_hist(data: dict):
    # Validate composite FK
    user = await users.lookup(
        tenant_id=data["tenant_id"],
        user_id=data["user_id"]
    )
    if not user:
        raise ValueError(f"User ({data['tenant_id']}, {data['user_id']}) not found")

    return await hist.insert(data)
```

---

## Bugs

(None currently tracked)
