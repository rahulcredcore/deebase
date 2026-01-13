#!/usr/bin/env python
"""Phase 16 Example: Data Management & Admin Interface

This example demonstrates the Phase 16 features:
1. Shared validation layer (ValidatedTable, apply_validators, validate_foreign_keys)
2. CLI data commands (deebase data insert/list/get/update/delete)
3. Admin web interface (deebase api serve --admin)

Run this example:
    uv run examples/phase16_data_admin.py

For CLI demo, initialize a project and run:
    deebase init
    deebase table create users id:int name:str email:str:unique --pk id
    deebase data insert users -f name=Alice -f email=alice@example.com
    deebase data list users
    deebase data get users 1
    deebase data update users 1 -f name=Bob
    deebase data delete users 1

For admin demo:
    deebase api init
    deebase api serve --admin
    # Visit http://127.0.0.1:8000/admin/
"""

import asyncio
from deebase import (
    Database,
    ForeignKey,
    apply_validators,
    validate_foreign_keys,
    ValidatedTable,
    ValidationError,
    ForeignKeyValidationError,
)


async def demo_shared_validation():
    """Demonstrate the shared validation layer."""
    print("\n" + "=" * 60)
    print("DEMO: Shared Validation Layer")
    print("=" * 60)

    db = Database("sqlite+aiosqlite:///:memory:")

    # Create tables
    class User:
        id: int
        name: str
        email: str
        status: str = "active"

    class Post:
        id: int
        author_id: ForeignKey[int, "user"]
        title: str
        content: str

    users = await db.create(User, pk="id")
    posts = await db.create(Post, pk="id")

    # --- 1. apply_validators: Transform and validate field values ---
    print("\n1. apply_validators() - Transform and validate fields")
    print("-" * 40)

    validators = {
        "name": lambda v: v.strip(),  # Strip whitespace
        "email": lambda v: v.lower(),  # Lowercase email
    }

    # Transform values
    data = {"name": "  Alice  ", "email": "ALICE@EXAMPLE.COM"}
    validated = apply_validators(data, validators)
    print(f"  Input:  {data}")
    print(f"  Output: {validated}")

    # Demonstrate validation error
    def validate_email(v):
        if "@" not in v:
            raise ValueError("Invalid email format")
        return v.lower()

    try:
        apply_validators({"email": "not-an-email"}, {"email": validate_email})
    except ValidationError as e:
        print(f"\n  ValidationError caught: {e.errors}")

    # --- 2. validate_foreign_keys: Check FK references exist ---
    print("\n2. validate_foreign_keys() - Check FK references")
    print("-" * 40)

    # Insert a user first
    alice = await users.insert({"name": "Alice", "email": "alice@example.com"})
    print(f"  Created user: {alice}")

    # Valid FK - no error
    post_data = {"author_id": alice["id"], "title": "Hello", "content": "World"}
    await validate_foreign_keys(db, posts, post_data)
    print(f"  Valid FK check passed for author_id={alice['id']}")

    # Invalid FK - raises ForeignKeyValidationError
    try:
        await validate_foreign_keys(db, posts, {"author_id": 999, "title": "Bad"})
    except ForeignKeyValidationError as e:
        print(f"  ForeignKeyValidationError: {e.errors[0]['message']}")

    # --- 3. ValidatedTable: Wrapper with automatic validation ---
    print("\n3. ValidatedTable - Wrapper with auto-validation")
    print("-" * 40)

    # Create a ValidatedTable wrapper
    validators = {
        "name": lambda v: v.strip(),
        "email": lambda v: v.lower(),
    }
    vusers = ValidatedTable(users, validators=validators)

    # Insert goes through validation
    bob = await vusers.insert({
        "name": "  Bob  ",  # Will be trimmed
        "email": "BOB@EXAMPLE.COM"  # Will be lowercased
    })
    print(f"  Inserted via ValidatedTable:")
    print(f"    name: '{bob['name']}' (was '  Bob  ')")
    print(f"    email: '{bob['email']}' (was 'BOB@EXAMPLE.COM')")

    # Read operations work unchanged
    all_users = await vusers()
    print(f"\n  Read operations work: {len(all_users)} users found")

    # Properties are accessible
    print(f"  Table name: {vusers.name}")
    print(f"  Schema preview: {vusers.schema[:50]}...")

    # --- 4. ValidatedTable with FK validation ---
    print("\n4. ValidatedTable with FK validation")
    print("-" * 40)

    # Wrap posts table with FK validation enabled
    vposts = ValidatedTable(posts, validate_fks=True)

    # Valid FK insert
    post = await vposts.insert({
        "author_id": alice["id"],
        "title": "My First Post",
        "content": "Hello from Alice!"
    })
    print(f"  Valid insert: {post['title']} by author_id={post['author_id']}")

    # Invalid FK insert
    try:
        await vposts.insert({
            "author_id": 999,
            "title": "Bad Post",
            "content": "This should fail"
        })
    except ForeignKeyValidationError as e:
        print(f"  Invalid insert blocked: {e.errors[0]['message']}")

    await db.close()
    print("\n  Done!")


async def demo_validated_table_xtra():
    """Demonstrate ValidatedTable with xtra() filtering."""
    print("\n" + "=" * 60)
    print("DEMO: ValidatedTable with xtra() Filtering")
    print("=" * 60)

    db = Database("sqlite+aiosqlite:///:memory:")

    class Product:
        id: int
        name: str
        category: str
        price: float

    products = await db.create(Product, pk="id")

    # Create ValidatedTable with price validator
    def validate_positive_price(v):
        if v <= 0:
            raise ValueError("Price must be positive")
        return round(v, 2)

    vproducts = ValidatedTable(products, validators={"price": validate_positive_price})

    # Insert some products
    await vproducts.insert({"name": "Laptop", "category": "electronics", "price": 999.999})
    await vproducts.insert({"name": "Phone", "category": "electronics", "price": 499.50})
    await vproducts.insert({"name": "Book", "category": "books", "price": 29.99})

    print("\n1. xtra() returns ValidatedTable")
    print("-" * 40)

    # Filter by category
    electronics = vproducts.xtra(category="electronics")

    # Still a ValidatedTable!
    print(f"  Type: {type(electronics).__name__}")

    # And still validates
    elec_records = await electronics()
    print(f"  Electronics count: {len(elec_records)}")
    for r in elec_records:
        print(f"    - {r['name']}: ${r['price']:.2f} (price was rounded)")

    await db.close()
    print("\n  Done!")


def show_cli_examples():
    """Show CLI data command examples."""
    print("\n" + "=" * 60)
    print("CLI Data Commands (Phase 16)")
    print("=" * 60)

    examples = """
1. Initialize project and create table:
   $ deebase init
   $ deebase table create users id:int name:str email:str:unique status:str:default=active --pk id

2. Insert records:
   $ deebase data insert users -f name=Alice -f email=alice@example.com
   $ deebase data insert users -j '{"name": "Bob", "email": "bob@example.com"}'
   $ deebase data insert users -F users.json  # Batch import

3. List records:
   $ deebase data list users                  # Table format
   $ deebase data list users --format json    # JSON format
   $ deebase data list users --format csv     # CSV format
   $ deebase data list users --limit 10       # Limit results

4. Get single record:
   $ deebase data get users 1                 # Get by PK
   $ deebase data get users 1 --format table  # Table format

5. Update record:
   $ deebase data update users 1 -f status=inactive
   $ deebase data update users 1 -j '{"name": "Alice Smith"}'

6. Delete record:
   $ deebase data delete users 1              # With confirmation
   $ deebase data delete users 1 -y           # Skip confirmation
"""
    print(examples)


def show_admin_examples():
    """Show admin interface examples."""
    print("\n" + "=" * 60)
    print("Admin Web Interface (Phase 16)")
    print("=" * 60)

    examples = """
1. Initialize API and start with admin:
   $ deebase api init
   $ deebase api serve --admin

2. Access the admin interface:
   - Dashboard: http://127.0.0.1:8000/admin/
   - Table list: http://127.0.0.1:8000/admin/users/
   - Create form: http://127.0.0.1:8000/admin/users/new
   - Edit form: http://127.0.0.1:8000/admin/users/1
   - Delete confirm: http://127.0.0.1:8000/admin/users/1/delete

3. Features:
   - Django-like interface for all tables
   - FK dropdown fields populated from parent tables
   - Validation using project's validators/
   - Pagination for list views
   - Delete confirmation
"""
    print(examples)


def show_validators_structure():
    """Show validators directory structure."""
    print("\n" + "=" * 60)
    print("Validators Directory Structure (Phase 16)")
    print("=" * 60)

    structure = """
After running `deebase init`, you get:

project/
├── .deebase/
├── validators/              # NEW in Phase 16
│   ├── __init__.py          # Validator registry
│   └── example.py           # Template with common validators
├── ...

Example validators/users.py:
```python
import re

def validate_email(value: str) -> str:
    if not re.match(r"^[^@]+@[^@]+\\.[^@]+$", value):
        raise ValueError("Invalid email format")
    return value.lower()

def validate_name(value: str) -> str:
    if not value.strip():
        raise ValueError("Name cannot be empty")
    return value.strip()

VALIDATORS = {
    "email": validate_email,
    "name": validate_name,
}
```

Register in validators/__init__.py:
```python
from . import users

VALIDATORS = {
    "users": users.VALIDATORS,
}
```

Now CLI and admin will use these validators automatically!
"""
    print(structure)


async def main():
    """Run all Phase 16 demos."""
    print("=" * 60)
    print("Phase 16: Data Management & Admin Interface")
    print("=" * 60)

    # Python API demos
    await demo_shared_validation()
    await demo_validated_table_xtra()

    # CLI and Admin info
    show_cli_examples()
    show_admin_examples()
    show_validators_structure()

    print("\n" + "=" * 60)
    print("Phase 16 Example Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
