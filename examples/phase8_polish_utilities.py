"""
Phase 8 Example: Production Polish & Utilities

This example demonstrates Phase 8 features:
- Enhanced exception system (6 exception types)
- Rich error context and attributes
- Error handling best practices
- Code generation utilities (dataclass_src, create_mod, create_mod_from_tables)
- Production-ready patterns
"""

import asyncio
import tempfile
import os
from pathlib import Path
from deebase import (
    Database,
    Text,
    NotFoundError,
    IntegrityError,
    ValidationError,
    SchemaError,
    InvalidOperationError,
    dataclass_src,
    create_mod,
    create_mod_from_tables,
)
from datetime import datetime


async def main():
    print("=" * 70)
    print("Phase 8: Production Polish & Utilities")
    print("=" * 70)
    print()

    # Create in-memory database
    db = Database("sqlite+aiosqlite:///:memory:")

    # =========================================================================
    # 1. Setup Tables for Examples
    # =========================================================================
    print("1. Setting Up Tables")
    print("-" * 70)

    class User:
        id: int
        username: str
        email: str
        created_at: datetime

    class Post:
        id: int
        user_id: int
        title: str
        content: Text
        published: bool
        created_at: datetime

    users = await db.create(User, pk='id')
    posts = await db.create(Post, pk='id')

    # Add unique constraints
    await db.q("CREATE UNIQUE INDEX idx_username ON user(username)")
    await db.q("CREATE UNIQUE INDEX idx_email ON user(email)")

    print(f"✓ Created tables: {users._name}, {posts._name}")
    print(f"✓ Added unique constraints on username and email")
    print()

    # Insert test data
    alice = await users.insert({
        "username": "alice",
        "email": "alice@example.com",
        "created_at": datetime.now()
    })
    print(f"✓ Inserted user: {alice['username']}")
    print()

    # =========================================================================
    # 2. NotFoundError - Record not found
    # =========================================================================
    print("\n2. NotFoundError - Record Not Found")
    print("-" * 70)

    print("Attempting to get non-existent user by PK:")
    try:
        user = await users[999]
    except NotFoundError as e:
        print(f"  ✗ {e.message}")
        print(f"    • table_name: {e.table_name}")
        print(f"    • filters: {e.filters}")
    print()

    print("Attempting lookup with non-existent email:")
    try:
        user = await users.lookup(email="unknown@example.com")
    except NotFoundError as e:
        print(f"  ✗ {e.message}")
        print(f"    • table_name: {e.table_name}")
        print(f"    • filters: {e.filters}")
    print()

    # =========================================================================
    # 3. IntegrityError - Constraint violations
    # =========================================================================
    print("\n3. IntegrityError - Constraint Violations")
    print("-" * 70)

    print("Attempting to insert duplicate username:")
    try:
        await users.insert({
            "username": "alice",  # Duplicate!
            "email": "alice2@example.com",
            "created_at": datetime.now()
        })
    except IntegrityError as e:
        print(f"  ✗ {e.message}")
        print(f"    • constraint: {e.constraint}")
        print(f"    • table_name: {e.table_name}")
    print()

    print("Attempting to insert duplicate email:")
    try:
        await users.insert({
            "username": "alice2",
            "email": "alice@example.com",  # Duplicate!
            "created_at": datetime.now()
        })
    except IntegrityError as e:
        print(f"  ✗ {e.message}")
        print(f"    • constraint: {e.constraint}")
        print(f"    • table_name: {e.table_name}")
    print()

    # =========================================================================
    # 4. ValidationError - Data validation failures
    # =========================================================================
    print("\n4. ValidationError - Data Validation Failures")
    print("-" * 70)

    print("Attempting update without primary key:")
    try:
        await users.update({"username": "bob", "email": "bob@example.com"})
    except ValidationError as e:
        print(f"  ✗ {e.message}")
        print(f"    • field: {e.field}")
        print(f"    • value: {e.value}")
    print()

    print("Testing xtra() filter violations:")
    admin_users = users.xtra(username="alice")
    try:
        await admin_users.insert({
            "username": "bob",  # Violates filter!
            "email": "bob@example.com",
            "created_at": datetime.now()
        })
    except ValidationError as e:
        print(f"  ✗ {e.message}")
        print(f"    • field: {e.field}")
        print(f"    • value: {e.value}")
    print()

    # =========================================================================
    # 5. SchemaError - Schema-related errors
    # =========================================================================
    print("\n5. SchemaError - Schema-Related Errors")
    print("-" * 70)

    print("Attempting lookup with unknown column:")
    try:
        await users.lookup(unknown_column="value")
    except SchemaError as e:
        print(f"  ✗ {e.message}")
        print(f"    • table_name: {e.table_name}")
        print(f"    • column_name: {e.column_name}")
    print()

    print("Attempting to create table with invalid primary key:")
    try:
        class Product:
            id: int
            name: str

        await db.create(Product, pk='product_id')  # Wrong PK name!
    except SchemaError as e:
        print(f"  ✗ {e.message}")
    print()

    # =========================================================================
    # 6. InvalidOperationError - Invalid operations
    # =========================================================================
    print("\n6. InvalidOperationError - Invalid Operations")
    print("-" * 70)

    # Create a view
    active_users = await db.create_view(
        "active_users",
        "SELECT * FROM user WHERE id > 0"
    )
    print(f"✓ Created view: {active_users._name}")
    print()

    print("Attempting INSERT on read-only view:")
    try:
        await active_users.insert({
            "username": "charlie",
            "email": "charlie@example.com",
            "created_at": datetime.now()
        })
    except NotImplementedError as e:
        print(f"  ✗ {str(e)}")
    print()

    print("Attempting UPDATE on read-only view:")
    try:
        await active_users.update({
            "id": 1,
            "username": "alice_updated",
            "email": "alice@example.com",
            "created_at": datetime.now()
        })
    except NotImplementedError as e:
        print(f"  ✗ {str(e)}")
    print()

    # =========================================================================
    # 7. Error Handling Best Practices
    # =========================================================================
    print("\n7. Error Handling Best Practices")
    print("-" * 70)

    # Pattern 1: Get or create
    print("Pattern: Get or Create User")

    async def get_or_create_user(email: str, username: str):
        try:
            return await users.lookup(email=email)
        except NotFoundError:
            try:
                return await users.insert({
                    "username": username,
                    "email": email,
                    "created_at": datetime.now()
                })
            except IntegrityError as e:
                # Race condition: another process created it
                print(f"    • Race condition: {e.message}")
                return await users.lookup(email=email)

    bob = await get_or_create_user("bob@example.com", "bob")
    print(f"  ✓ User: {bob['username']} ({bob['email']})")

    # Try again - should return existing
    bob2 = await get_or_create_user("bob@example.com", "bob")
    print(f"  ✓ User (cached): {bob2['username']} ({bob2['email']})")
    print()

    # Pattern 2: Safe update with validation
    print("Pattern: Safe Update with Validation")

    async def update_user_safe(user_id: int, updates: dict):
        try:
            user = await users[user_id]
        except NotFoundError:
            return {"error": "User not found"}

        try:
            user.update(updates)
            return await users.update(user)
        except ValidationError as e:
            return {"error": f"Invalid {e.field}: {e.value}"}
        except IntegrityError as e:
            return {"error": f"Constraint violation: {e.constraint}"}

    result = await update_user_safe(1, {"username": "alice_updated"})
    if "error" not in result:
        print(f"  ✓ Updated user: {result['username']}")
    print()

    # Pattern 3: Safe lookup
    print("Pattern: Safe Lookup (returns None on error)")

    async def safe_lookup(**filters):
        try:
            return await users.lookup(**filters)
        except SchemaError as e:
            print(f"    • Unknown column: {e.column_name}")
            return None
        except NotFoundError:
            return None

    user = await safe_lookup(username="alice_updated")
    if user:
        print(f"  ✓ Found: {user['username']}")

    user = await safe_lookup(username="nonexistent")
    if not user:
        print(f"  ✓ Not found: None")
    print()

    # =========================================================================
    # 8. Code Generation: dataclass_src()
    # =========================================================================
    print("\n8. Code Generation: dataclass_src()")
    print("-" * 70)

    # Generate dataclass from table
    UserDC = users.dataclass()
    print("Generated dataclass from 'users' table:")
    print()

    # Get source code
    src = dataclass_src(UserDC)
    print(src)
    print()

    # =========================================================================
    # 9. Code Generation: create_mod()
    # =========================================================================
    print("\n9. Code Generation: create_mod()")
    print("-" * 70)

    # Generate dataclasses
    UserDC = users.dataclass()
    PostDC = posts.dataclass()

    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        temp_models_path = f.name

    try:
        # Export to module file
        create_mod(
            temp_models_path,
            UserDC,
            PostDC,
            overwrite=True
        )

        print(f"✓ Created module file: {temp_models_path}")
        print()

        # Read and display the generated file
        print("Generated content:")
        print("-" * 70)
        with open(temp_models_path, 'r') as f:
            content = f.read()
            print(content)
        print("-" * 70)
        print()
    finally:
        # Clean up
        if os.path.exists(temp_models_path):
            os.unlink(temp_models_path)

    # =========================================================================
    # 10. Code Generation: create_mod_from_tables()
    # =========================================================================
    print("\n10. Code Generation: create_mod_from_tables()")
    print("-" * 70)

    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        temp_models_path2 = f.name

    try:
        # Export directly from tables
        create_mod_from_tables(
            temp_models_path2,
            users,
            posts,
            overwrite=True
        )

        print(f"✓ Created module file from tables: {temp_models_path2}")
        print()

        # Read and display
        print("Generated content:")
        print("-" * 70)
        with open(temp_models_path2, 'r') as f:
            content = f.read()
            # Show first 30 lines
            lines = content.split('\n')[:30]
            print('\n'.join(lines))
            if len(content.split('\n')) > 30:
                print("...")
        print("-" * 70)
        print()
    finally:
        # Clean up
        if os.path.exists(temp_models_path2):
            os.unlink(temp_models_path2)

    # =========================================================================
    # 11. Production-Ready Pattern: Complete CRUD with Error Handling
    # =========================================================================
    print("\n11. Production-Ready Pattern: Complete CRUD with Error Handling")
    print("-" * 70)

    async def create_post_safe(user_id: int, title: str, content: str):
        """Create a post with comprehensive error handling."""
        try:
            # Verify user exists
            user = await users[user_id]

            # Create post
            post = await posts.insert({
                "user_id": user_id,
                "title": title,
                "content": content,
                "published": False,
                "created_at": datetime.now()
            })
            return {"success": True, "post": post}
        except NotFoundError:
            return {"success": False, "error": f"User {user_id} not found"}
        except ValidationError as e:
            return {"success": False, "error": f"Invalid {e.field}: {e.value}"}
        except IntegrityError as e:
            return {"success": False, "error": f"Constraint violation: {e.constraint}"}

    # Test the pattern
    print("Creating post for user 1:")
    result = await create_post_safe(
        user_id=1,
        title="My First Post",
        content="This is the content of my first post!"
    )
    if result["success"]:
        post = result['post']
        title = post['title'] if isinstance(post, dict) else post.title
        print(f"  ✓ Created post: {title}")
    else:
        print(f"  ✗ Error: {result['error']}")
    print()

    print("Creating post for non-existent user:")
    result = await create_post_safe(
        user_id=999,
        title="Ghost Post",
        content="This should fail"
    )
    if result["success"]:
        post = result['post']
        title = post['title'] if isinstance(post, dict) else post.title
        print(f"  ✓ Created post: {title}")
    else:
        print(f"  ✗ Error: {result['error']}")
    print()

    # Clean up
    await db.close()

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 70)
    print("Phase 8 Production Polish & Utilities - Complete!")
    print("=" * 70)
    print()
    print("Key Takeaways:")
    print()
    print("Exception System:")
    print("  • NotFoundError - Record not found (table_name, filters)")
    print("  • IntegrityError - Constraint violations (constraint, table_name)")
    print("  • ValidationError - Data validation failures (field, value)")
    print("  • SchemaError - Schema errors (table_name, column_name)")
    print("  • InvalidOperationError - Invalid operations (operation, target)")
    print("  • ConnectionError - Database connection issues (database_url)")
    print()
    print("Code Generation:")
    print("  • dataclass_src(dc) - Generate source code from dataclass")
    print("  • create_mod(path, *dcs) - Export dataclasses to module file")
    print("  • create_mod_from_tables(path, *tables) - Export tables to module")
    print()
    print("Best Practices:")
    print("  • Use specific exception types for targeted error handling")
    print("  • Access exception attributes for rich error context")
    print("  • Implement get-or-create patterns with race condition handling")
    print("  • Return error dicts for API-friendly error responses")
    print("  • Generate dataclass modules for type-safe application code")


if __name__ == "__main__":
    asyncio.run(main())
