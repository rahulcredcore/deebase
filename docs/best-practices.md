# DeeBase Best Practices & Design Decisions

This guide helps you make informed decisions when using DeeBase, explaining the consequences of different approaches and when to use each feature.

## Table of Contents

- [Dict vs Dataclass: Choosing Your Programming Style](#dict-vs-dataclass-choosing-your-programming-style)
- [Reflection: When and How](#reflection-when-and-how)
- [Table and View Creation Patterns](#table-and-view-creation-patterns)
- [Maintaining Consistency](#maintaining-consistency)
- [Error Handling Strategy](#error-handling-strategy)
- [Performance Considerations](#performance-considerations)
- [Schema Evolution](#schema-evolution)

---

## Dict vs Dataclass: Choosing Your Programming Style

DeeBase supports two programming styles: dictionary-based and dataclass-based. Understanding when to use each is crucial for maintaining a consistent codebase.

### Dictionary-Based Operations (Default)

**When to use:**
- Quick scripts and prototypes
- Jupyter notebooks and REPLs
- Dynamic data where fields may vary
- Working with JSON-like data
- When you don't need type checking

**How it works:**
```python
users = await db.create(User, pk='id')

# All operations return dicts by default
user = await users.insert({"name": "Alice", "email": "alice@example.com"})
print(user['name'])  # Dictionary access

all_users = await users()
for u in all_users:
    print(u['name'])  # Each is a dict
```

**Characteristics:**
- ✅ Simple and flexible
- ✅ No setup required
- ✅ Easy to serialize to JSON
- ❌ No type checking
- ❌ No IDE autocomplete
- ❌ Typos in keys fail at runtime

### Dataclass-Based Operations

**When to use:**
- Production applications
- Large codebases with multiple developers
- When you want IDE autocomplete and type checking
- When you need clear contracts between functions
- Working with typed frameworks (FastAPI, etc.)

**How it works:**
```python
users = await db.create(User, pk='id')

# Enable dataclass mode
UserDC = users.dataclass()

# All operations now return dataclass instances
user = await users.insert(UserDC(name="Alice", email="alice@example.com"))
print(user.name)  # Attribute access with autocomplete

all_users = await users()
for u in all_users:
    print(u.name)  # Each is a UserDC instance
```

**Characteristics:**
- ✅ Type checking and IDE support
- ✅ Catches field typos at development time
- ✅ Self-documenting code
- ✅ Better refactoring support
- ❌ Requires calling `.dataclass()` first
- ❌ Slightly more verbose

### Making the Choice

**Use dicts when:**
- You're exploring data interactively
- The structure is dynamic or varies
- You're prototyping quickly
- You frequently convert to/from JSON

**Use dataclasses when:**
- You're building production applications
- Multiple developers work on the codebase
- You want compile-time guarantees
- The schema is well-defined and stable

### Mixed Usage: Consequences and Pitfalls

**⚠️ Warning:** Mixing dict and dataclass operations can lead to confusion!

```python
users = await db.create(User, pk='id')

# Insert returns dict (default)
user1 = await users.insert({"name": "Alice", "email": "alice@example.com"})
print(user1['name'])  # ✅ Works

# Enable dataclass mode
UserDC = users.dataclass()

# Now INSERT returns dataclass instances
user2 = await users.insert({"name": "Bob", "email": "bob@example.com"})
print(user2.name)  # ✅ Works
print(user2['name'])  # ❌ TypeError: 'User' object is not subscriptable

# SELECT also returns dataclass instances now
all_users = await users()
print(all_users[0].name)  # ✅ Works if you've called .dataclass()
print(all_users[0]['name'])  # ❌ Fails after .dataclass()
```

**The Rule:** Once you call `.dataclass()`, ALL operations on that table return dataclass instances.

---

## Reflection: When and How

Reflection is the process of loading existing database schema into DeeBase. Understanding when to reflect is essential for working with existing databases.

### Table Creation: No Reflection Needed

When you create a table with `db.create()`, it's **automatically cached**:

```python
# Create table - automatically cached
users = await db.create(User, pk='id')

# Immediately available via db.t
users_again = db.t.users  # ✅ Works immediately (sync, no await)
```

**When to use:** Creating new tables from Python classes.

**Reflection needed:** ❌ No

### Raw SQL Creation: Reflection Required

When you create tables with raw SQL, you must **explicitly reflect**:

```python
# Create with raw SQL
await db.q("CREATE TABLE products (id INT PRIMARY KEY, name TEXT)")

# NOT available yet
try:
    products = db.t.products  # ❌ AttributeError
except AttributeError:
    pass

# Reflect to load the table
await db.reflect_table('products')

# Now available
products = db.t.products  # ✅ Works
```

**When to use:** Working with tables created outside DeeBase.

**Reflection needed:** ✅ Yes - call `db.reflect_table(name)`

### Existing Databases: Bulk Reflection

When connecting to an existing database with many tables:

```python
# Connect to existing database
db = Database("sqlite+aiosqlite:///legacy.db")

# Reflect ALL tables at once
await db.reflect()

# All tables now available
users = db.t.users
posts = db.t.posts
comments = db.t.comments
```

**When to use:** Working with databases created by other tools or applications.

**Reflection needed:** ✅ Yes - call `db.reflect()`

### Views: Creation vs Reflection

#### View Creation: No Reflection Needed

```python
# Create view with DeeBase
view = await db.create_view(
    "active_users",
    "SELECT * FROM users WHERE active = 1"
)

# Immediately available
view_again = db.v.active_users  # ✅ Works immediately (sync, no await)
```

**When to use:** Creating new views from within your application.

**Reflection needed:** ❌ No

#### View Reflection: When Views Exist

```python
# View was created outside DeeBase (raw SQL, migration tool, etc.)
await db.q("CREATE VIEW user_emails AS SELECT id, name, email FROM users")

# NOT available yet
try:
    view = db.v.user_emails  # ❌ AttributeError
except AttributeError:
    pass

# Reflect to load the view
await db.reflect_view('user_emails')

# Now available
view = db.v.user_emails  # ✅ Works
```

**When to use:** Working with views created by raw SQL or external tools.

**Reflection needed:** ✅ Yes - call `db.reflect_view(name)`

### Reflection Decision Tree

```
Did you create the table/view with db.create() or db.create_view()?
├─ YES → No reflection needed, immediately available via db.t or db.v
└─ NO → Created with raw SQL or external tool?
    └─ YES → Reflection required
        ├─ Single table/view → await db.reflect_table(name) or await db.reflect_view(name)
        └─ Multiple tables → await db.reflect()
```

---

## Table and View Creation Patterns

### Pattern 1: Pure Python (Recommended for New Projects)

```python
# Define schema in Python
class User:
    id: int
    name: str
    email: str

class Post:
    id: int
    user_id: int
    title: str
    content: Text

# Create tables
users = await db.create(User, pk='id')
posts = await db.create(Post, pk='id')

# Create views
popular_posts = await db.create_view(
    "popular_posts",
    "SELECT * FROM post WHERE views > 1000"
)

# Everything is immediately available
users = db.t.users
posts = db.t.posts
view = db.v.popular_posts
```

**Pros:**
- ✅ Type-safe schema definition
- ✅ No reflection needed
- ✅ Self-documenting
- ✅ Version controlled

**Cons:**
- ❌ Can't use advanced SQL features (CHECK constraints, triggers, etc.)
- ❌ Must match Python type system

### Pattern 2: Raw SQL + Reflection (For Complex Schemas)

```python
# Create with raw SQL for advanced features
await db.q("""
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CHECK (length(email) > 3)
    )
""")

# Reflect to load
await db.reflect_table('users')

# Now use Python API
users = db.t.users
await users.insert({"email": "alice@example.com"})
```

**Pros:**
- ✅ Full SQL features (CHECK, DEFAULT, triggers, etc.)
- ✅ Can use database-specific features
- ✅ Direct control over schema

**Cons:**
- ❌ Requires reflection step
- ❌ Schema not in Python code
- ❌ No type checking during table creation

### Pattern 3: Hybrid (Best of Both Worlds)

```python
# Use Python for simple tables
users = await db.create(User, pk='id')

# Use raw SQL for complex constraints
await db.q("""
    CREATE UNIQUE INDEX idx_email ON user(email)
""")
await db.q("""
    CREATE TRIGGER user_updated
    AFTER UPDATE ON user
    BEGIN
        UPDATE user SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END
""")
```

**Pros:**
- ✅ Python schema definition
- ✅ Advanced SQL when needed
- ✅ No reflection for base tables

**Cons:**
- ❌ Schema split between Python and SQL
- ❌ Requires understanding both approaches

---

## Maintaining Consistency

### Dataclass Consistency Strategy

**Problem:** Once you call `.dataclass()` on a table, operations return dataclass instances. If you call it inconsistently, your code will have mixed types.

**Solution: Call `.dataclass()` immediately after table creation or reflection**

```python
# ✅ GOOD: Establish mode early
users = await db.create(User, pk='id')
UserDC = users.dataclass()  # Enable immediately

posts = await db.create(Post, pk='id')
PostDC = posts.dataclass()  # Enable immediately

# All subsequent operations are consistent
user = await users.insert(UserDC(...))  # Returns UserDC
users_list = await users()  # Returns List[UserDC]
```

```python
# ❌ BAD: Mixing dict and dataclass
users = await db.create(User, pk='id')

# Some operations with dicts
user1 = await users.insert({"name": "Alice"})  # Returns dict
print(user1['name'])  # Works

# Later, enable dataclass
UserDC = users.dataclass()

# Now operations return dataclass
user2 = await users.insert({"name": "Bob"})  # Returns UserDC
print(user2['name'])  # ❌ Fails! Need user2.name
```

### Recommended Initialization Pattern

```python
async def init_database():
    """Initialize database with consistent configuration."""
    db = Database("sqlite+aiosqlite:///myapp.db")

    # Create all tables
    users = await db.create(User, pk='id')
    posts = await db.create(Post, pk='id')
    comments = await db.create(Comment, pk='id')

    # Enable dataclass mode for all tables (if desired)
    UserDC = users.dataclass()
    PostDC = posts.dataclass()
    CommentDC = comments.dataclass()

    # Return configured database
    return db, (UserDC, PostDC, CommentDC)

# Use it
db, (UserDC, PostDC, CommentDC) = await init_database()

# All operations are now consistently typed
```

### Per-Module Consistency

If you're building a large application, maintain consistency per module:

```python
# users_module.py
class User:
    id: int
    name: str
    email: str

async def init_users(db):
    users = await db.create(User, pk='id')
    UserDC = users.dataclass()  # Always dataclass in this module
    return users, UserDC

# In application code
users, UserDC = await init_users(db)
# All user operations use UserDC
```

---

## Error Handling Strategy

### Exception Hierarchy

DeeBase provides specific exception types for different error scenarios:

```python
DeeBaseError (base)
├── NotFoundError (record not found)
├── IntegrityError (constraint violations)
├── ValidationError (data validation failures)
├── SchemaError (schema-related errors)
├── ConnectionError (database connection issues)
└── InvalidOperationError (invalid operations)
```

### When to Catch Which Exception

#### `NotFoundError`: Optional Records

**When to catch:** When a missing record is acceptable.

```python
# Pattern: Optional lookup
try:
    user = await users.lookup(email=email)
except NotFoundError:
    user = None

if user:
    print(f"Found: {user.name}")
else:
    print("User not found, creating new...")
    user = await users.insert({"email": email, "name": name})
```

**When NOT to catch:** When the record must exist (let it propagate).

#### `IntegrityError`: Constraint Violations

**When to catch:** When duplicates or constraint violations are possible.

```python
# Pattern: Handle duplicate gracefully
try:
    user = await users.insert({"email": email, "name": name})
except IntegrityError as e:
    if e.constraint == "unique":
        print(f"Email {email} already exists")
        user = await users.lookup(email=email)
    else:
        raise  # Re-raise other integrity errors
```

**When NOT to catch:** When constraints should never be violated (programming error).

#### `ValidationError`: Input Validation

**When to catch:** When processing user input.

```python
# Pattern: Validate user input
try:
    updated_user = await users.update(user_data)
except ValidationError as e:
    return {"error": f"Invalid {e.field}: {e.value}"}
```

**When NOT to catch:** When data comes from trusted internal sources.

#### `SchemaError`: Development vs Production

**When to catch:** Rarely - usually indicates a programming error.

```python
# Usually let it fail during development
user = await users.lookup(email=email)  # Typo causes SchemaError

# But can catch for dynamic queries
try:
    result = await users.lookup(**dynamic_filters)
except SchemaError as e:
    print(f"Invalid column: {e.column_name}")
    result = None
```

### Error Handling Patterns

#### Pattern 1: Get-or-Create with Race Condition Handling

```python
async def get_or_create_user(email: str, name: str):
    """Get existing user or create new one, handling race conditions."""
    try:
        # Try to find existing
        return await users.lookup(email=email)
    except NotFoundError:
        # Doesn't exist, create it
        try:
            return await users.insert({"email": email, "name": name})
        except IntegrityError:
            # Another process created it between lookup and insert
            # Try one more time
            return await users.lookup(email=email)
```

#### Pattern 2: Safe Update with Validation

```python
async def safe_update_user(user_id: int, updates: dict) -> dict:
    """Update user with comprehensive error handling."""
    try:
        # Verify user exists
        user = await users[user_id]

        # Apply updates
        user.update(updates)

        # Attempt update
        return {"success": True, "user": await users.update(user)}

    except NotFoundError:
        return {"success": False, "error": "User not found"}
    except ValidationError as e:
        return {"success": False, "error": f"Invalid {e.field}: {e.value}"}
    except IntegrityError as e:
        return {"success": False, "error": f"Constraint violated: {e.constraint}"}
```

#### Pattern 3: Bulk Operations with Error Collection

```python
async def bulk_insert_users(user_list: list[dict]) -> dict:
    """Insert multiple users, collecting errors."""
    results = {"success": [], "errors": []}

    for user_data in user_list:
        try:
            user = await users.insert(user_data)
            results["success"].append(user)
        except IntegrityError as e:
            results["errors"].append({
                "data": user_data,
                "error": f"Constraint {e.constraint} violated"
            })
        except ValidationError as e:
            results["errors"].append({
                "data": user_data,
                "error": f"Invalid {e.field}: {e.value}"
            })

    return results
```

---

## Transaction Management

Understanding when and how to use transactions is critical for data integrity and performance.

### When to Use Transactions

**Use transactions when:**

1. **Multi-operation atomicity** - All operations must succeed or fail together
   ```python
   async with db.transaction():
       user = await users.insert({"name": "Alice"})
       profile = await profiles.insert({"user_id": user['id']})
   # Both succeed or both fail
   ```

2. **Financial operations** - Money transfers, account balances
   ```python
   async with db.transaction():
       sender['balance'] -= amount
       receiver['balance'] += amount
       await accounts.update(sender)
       await accounts.update(receiver)
   ```

3. **Inventory management** - Stock updates, order fulfillment
   ```python
   async with db.transaction():
       product = await products[product_id]
       product['stock'] -= quantity
       await products.update(product)
       await orders.insert({"product_id": product_id, "quantity": quantity})
   ```

4. **Read-modify-write** - Prevent race conditions
   ```python
   async with db.transaction():
       counter = await counters[1]
       counter['value'] += 1
       await counters.update(counter)
   # Atomic increment - no lost updates
   ```

5. **Batch operations** - Create/update multiple related records
   ```python
   async with db.transaction():
       order = await orders.insert({"total": 0.0})
       for item in items:
           await order_items.insert({"order_id": order['id'], **item})
   ```

### When NOT to Use Transactions

**Avoid transactions for:**

1. **Single operations** - Each operation is already atomic
   ```python
   # ❌ Unnecessary transaction
   async with db.transaction():
       user = await users.insert({"name": "Bob"})

   # ✅ Single operation is already atomic
   user = await users.insert({"name": "Bob"})
   ```

2. **Read-only queries** - No benefit from transactions
   ```python
   # ❌ Unnecessary transaction
   async with db.transaction():
       users_list = await users()

   # ✅ Direct query
   users_list = await users()
   ```

3. **DDL operations** - CREATE TABLE, ALTER TABLE (not transactional in most databases)
   ```python
   # ❌ DDL not transactional
   async with db.transaction():
       await db.q("CREATE TABLE products (id INT)")

   # ✅ DDL outside transactions
   await db.q("CREATE TABLE products (id INT)")
   ```

4. **Long-running operations** - Hold locks minimally
   ```python
   # ❌ Long transaction holds locks
   async with db.transaction():
       for i in range(10000):
           await users.insert({"name": f"User {i}"})

   # ✅ Smaller batches or no transaction
   for i in range(10000):
       await users.insert({"name": f"User {i}"})
   ```

### Common Transaction Patterns

#### Pattern 1: Money Transfer (Atomic Update)

```python
async def transfer_money(from_id: int, to_id: int, amount: float):
    """Transfer money atomically between accounts."""
    async with db.transaction():
        # Get both accounts
        sender = await accounts[from_id]
        receiver = await accounts[to_id]

        # Validate
        if sender['balance'] < amount:
            raise ValueError("Insufficient funds")

        # Update both
        sender['balance'] -= amount
        receiver['balance'] += amount

        await accounts.update(sender)
        await accounts.update(receiver)

    # Commits together - both succeed or both fail
```

#### Pattern 2: Create with Related Records

```python
async def create_user_with_profile(user_data: dict, profile_data: dict):
    """Create user and profile atomically."""
    async with db.transaction():
        # Create user
        user = await users.insert(user_data)

        # Create profile with user_id
        profile_data['user_id'] = user['id']
        profile = await profiles.insert(profile_data)

        return user, profile

    # If profile creation fails, user creation rolls back
```

#### Pattern 3: Batch Insert with Validation

```python
async def create_order(order_data: dict, items: list[dict]):
    """Create order with items, validating stock."""
    async with db.transaction():
        # Validate all items have stock
        for item in items:
            product = await products[item['product_id']]
            if product['stock'] < item['quantity']:
                raise ValueError(f"Insufficient stock for {product['name']}")

        # Create order
        order = await orders.insert(order_data)

        # Create items and decrement stock
        for item in items:
            item['order_id'] = order['id']
            await order_items.insert(item)

            product = await products[item['product_id']]
            product['stock'] -= item['quantity']
            await products.update(product)

        return order

    # All or nothing - order, items, and stock updates
```

#### Pattern 4: Safe Counter Increment

```python
async def increment_counter(counter_id: int):
    """Atomically increment a counter."""
    async with db.transaction():
        counter = await counters[counter_id]
        counter['value'] += 1
        await counters.update(counter)
        return counter['value']

    # No lost updates - transaction prevents race conditions
```

### Error Handling in Transactions

```python
# Pattern: Catch specific errors, let transaction rollback
async def safe_transfer(from_id: int, to_id: int, amount: float) -> dict:
    try:
        async with db.transaction():
            sender = await accounts[from_id]
            receiver = await accounts[to_id]

            if sender['balance'] < amount:
                raise ValueError("Insufficient funds")

            sender['balance'] -= amount
            receiver['balance'] += amount

            await accounts.update(sender)
            await accounts.update(receiver)

        return {"success": True}

    except NotFoundError as e:
        return {"success": False, "error": f"Account not found: {e.table_name}"}
    except ValueError as e:
        return {"success": False, "error": str(e)}
    # Any exception causes automatic rollback
```

### Performance Considerations

**Transactions add overhead:**
- Locks held for transaction duration
- Rollback overhead on failure
- Database transaction log overhead

**Best practices:**
1. Keep transactions short
2. Don't do I/O inside transactions (API calls, file operations)
3. Don't use transactions for read-only operations
4. Consider optimistic locking for low-contention scenarios

```python
# ❌ BAD: Long transaction with I/O
async with db.transaction():
    user = await users.insert({"name": "Alice"})
    # Don't do this in a transaction!
    await send_email(user['email'])
    await log_to_external_service(user)

# ✅ GOOD: Short transaction, then I/O
async with db.transaction():
    user = await users.insert({"name": "Alice"})

# I/O after transaction
await send_email(user['email'])
await log_to_external_service(user)
```

### Backward Compatibility

Transactions are **completely optional**. Existing code works without changes:

```python
# Without transactions (each operation auto-commits)
user = await users.insert({"name": "Alice"})
await users.update(user)

# With transactions (explicit control)
async with db.transaction():
    user = await users.insert({"name": "Bob"})
    await users.update(user)
```

All CRUD operations automatically participate in active transactions - no code changes needed.

---

## Performance Considerations

### Connection Management

**Always close connections when done:**

```python
# Manual management
db = Database("sqlite+aiosqlite:///myapp.db")
try:
    # Use database
    users = await db.create(User, pk='id')
    # ...
finally:
    await db.close()

# Or use context manager (recommended)
async with Database("sqlite+aiosqlite:///myapp.db") as db:
    users = await db.create(User, pk='id')
    # Connection automatically closed
```

### Bulk Operations

**Use bulk inserts when possible:**

```python
# ❌ Slow: Many individual inserts
for user_data in user_list:
    await users.insert(user_data)

# ✅ Fast: Bulk insert with raw SQL
await db.q("""
    INSERT INTO users (name, email) VALUES
    (?, ?), (?, ?), (?, ?)
""", *flattened_values)
```

### Reflection Costs

**Reflection is expensive - do it once:**

```python
# ❌ Expensive: Reflect on every request
async def get_users():
    await db.reflect()  # Don't do this repeatedly!
    return await db.t.users()

# ✅ Efficient: Reflect once at startup
async def init_app():
    db = Database("sqlite+aiosqlite:///myapp.db")
    await db.reflect()  # Once at startup
    return db

db = await init_app()

async def get_users():
    return await db.t.users()  # Use cached table
```

### Dataclass vs Dict Performance

**Dict operations are slightly faster, but difference is negligible:**

```python
# Dicts: Minimal overhead
users_list = await users()  # Returns List[dict]

# Dataclasses: Small overhead for instantiation
UserDC = users.dataclass()
users_list = await users()  # Returns List[UserDC]
```

**In practice:** Choose based on type safety needs, not performance.

---

## Schema Evolution

### Adding Columns

**Option 1: Raw SQL + Reflection (Recommended)**

```python
# Add column with SQL
await db.q("ALTER TABLE users ADD COLUMN phone TEXT")

# Reflect to pick up changes
await db.reflect_table('users')

# Now usable
user = await db.t.users.insert({"name": "Alice", "phone": "555-1234"})
```

**Option 2: Recreate Table (Development Only)**

```python
# Drop and recreate (loses data!)
await users.drop()

class User:
    id: int
    name: str
    email: str
    phone: str  # New field

users = await db.create(User, pk='id')
```

### Migrations

**Recommended: Use a migration tool alongside DeeBase**

```python
# Use alembic, yoyo, or similar for migrations
# Then reflect the results in DeeBase

async def init_db_after_migrations():
    db = Database("sqlite+aiosqlite:///myapp.db")
    # Migrations already ran, just reflect
    await db.reflect()
    return db
```

---

## Summary: Quick Decision Guide

| Scenario | Recommendation |
|----------|----------------|
| **Quick script** | Use dicts |
| **Production app** | Use dataclasses |
| **Creating new tables** | Use `db.create()` - no reflection needed |
| **Existing database** | Use `db.reflect()` on startup |
| **Raw SQL table creation** | Follow with `db.reflect_table(name)` |
| **Creating views** | Use `db.create_view()` - no reflection needed |
| **Existing views** | Use `db.reflect_view(name)` |
| **Want type safety** | Call `.dataclass()` immediately after creation/reflection |
| **Need flexibility** | Stick with dicts |
| **Mixed team** | Establish convention early (all dict OR all dataclass per table) |
| **User input** | Catch `ValidationError` and `IntegrityError` |
| **Optional records** | Catch `NotFoundError` |
| **Schema errors** | Usually let fail (programming error) |
| **Multiple tables** | Initialize all at once, configure consistently |

---

## Getting Help

Still unsure about a decision?

1. Check the [API Reference](api_reference.md) for detailed method documentation
2. See [Implemented Features](implemented.md) for examples of each feature
3. Review the [examples/](../examples/) folder for runnable code
4. Read [How It Works](how-it-works.md) for technical deep dives

**Rule of Thumb:** When in doubt, start simple (dicts, no dataclass) and add complexity (dataclass, types) when you need it. DeeBase is designed to support both styles seamlessly.
