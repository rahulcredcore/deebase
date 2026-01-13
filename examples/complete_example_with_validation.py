"""
Complete Example: Blog with Validation & Admin Interface

This example demonstrates DeeBase Phase 16 features alongside core capabilities:
- Shared validation layer (ValidatedTable, apply_validators, validate_foreign_keys)
- CLI data commands (deebase data insert/list/get/update/delete)
- Admin web interface (deebase api serve --admin)
- Project validators directory (validators/)

For CLI data command usage, see the comments throughout this file.
For admin interface, run: deebase api serve --admin

This example covers:
- Phase 1-12: Core database features (CRUD, FK, indexes, views, transactions)
- Phase 15: FastAPI integration with CRUD routers
- Phase 16: Validation layer, CLI data commands, admin interface
"""

import asyncio
from typing import Optional
from datetime import datetime
from dataclasses import dataclass
from deebase import (
    Database, Text, ForeignKey, Index,
    NotFoundError, IntegrityError, ValidationError,
    # Phase 16 validation exports
    apply_validators,
    validate_foreign_keys,
    ValidatedTable,
    ForeignKeyValidationError,
)


# =============================================================================
# Validator Functions
# =============================================================================
# These are the same validators you'd put in validators/users.py

def validate_email(value: str) -> str:
    """Validate and normalize email addresses."""
    if not value:
        return value
    if "@" not in value:
        raise ValueError("Invalid email format - must contain @")
    return value.lower().strip()


def validate_name(value: str) -> str:
    """Validate and normalize names."""
    if not value:
        return value
    value = value.strip()
    if len(value) < 2:
        raise ValueError("Name must be at least 2 characters")
    return value


def validate_title(value: str) -> str:
    """Validate and normalize titles."""
    if not value:
        return value
    value = value.strip()
    if len(value) < 5:
        raise ValueError("Title must be at least 5 characters")
    return value[:200]  # Limit to 200 chars


def validate_slug(value: str) -> str:
    """Generate and validate URL slugs."""
    if not value:
        return value
    # Normalize: lowercase, replace spaces with dashes
    return value.lower().strip().replace(" ", "-")[:50]


# =============================================================================
# Table Definitions
# =============================================================================

class Author:
    id: int
    name: str
    email: str
    bio: Optional[Text]
    status: str = "active"


class Category:
    id: int
    name: str
    slug: str


class Post:
    id: int
    title: str
    slug: str
    content: Text
    excerpt: Optional[str]
    author_id: ForeignKey[int, "author"]
    category_id: ForeignKey[int, "category"]
    metadata: dict
    published: bool = False
    view_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime]


class Comment:
    id: int
    post_id: ForeignKey[int, "post"]
    author_name: str
    content: Text
    approved: bool = False
    created_at: datetime


async def main():
    print("=" * 70)
    print("Complete Example: Blog with Validation & Admin Interface")
    print("Demonstrating Phase 16 features + core DeeBase capabilities")
    print("=" * 70)
    print()

    db = Database("sqlite+aiosqlite:///:memory:")

    # =========================================================================
    # Setup: Create Tables with Indexes
    # =========================================================================
    print("1. Creating tables with indexes")
    print("-" * 70)

    authors = await db.create(
        Author, pk='id', if_not_exists=True,
        indexes=[Index("idx_author_email", "email", unique=True)]
    )

    categories = await db.create(
        Category, pk='id', if_not_exists=True,
        indexes=["slug"]
    )

    posts = await db.create(
        Post, pk='id', if_not_exists=True,
        indexes=[
            Index("idx_post_slug", "slug", unique=True),
            ("author_id", "created_at"),
            "published",
        ]
    )

    comments = await db.create(
        Comment, pk='id', if_not_exists=True,
        indexes=[("post_id", "created_at")]
    )

    await db.q("PRAGMA foreign_keys = ON")
    print("   Created: authors, categories, posts, comments")
    print("   Enabled: Foreign key enforcement")
    print()

    # =========================================================================
    # Phase 16: apply_validators() - Transform and validate field values
    # =========================================================================
    print("2. Phase 16: apply_validators() - Field transformation & validation")
    print("-" * 70)

    # Define validators for authors table
    author_validators = {
        "name": validate_name,
        "email": validate_email,
    }

    # Test with raw data (simulating CLI or form input)
    raw_data = {
        "name": "  Alice Smith  ",  # Has leading/trailing whitespace
        "email": "ALICE@EXAMPLE.COM",  # Uppercase
        "bio": "Tech writer and Python enthusiast"
    }

    print(f"   Raw input: name='{raw_data['name']}', email='{raw_data['email']}'")

    validated_data = apply_validators(raw_data, author_validators)

    print(f"   Validated: name='{validated_data['name']}', email='{validated_data['email']}'")

    # Test validation error
    print("\n   Testing validation error:")
    try:
        apply_validators({"email": "not-an-email"}, author_validators)
    except ValidationError as e:
        print(f"   Caught ValidationError: {e.errors}")
    print()

    # =========================================================================
    # Phase 16: ValidatedTable - Wrapper with automatic validation
    # =========================================================================
    print("3. Phase 16: ValidatedTable - Automatic validation on writes")
    print("-" * 70)

    # Wrap the authors table with validators
    vauthors = ValidatedTable(authors, validators=author_validators)

    # Insert through ValidatedTable - validation happens automatically
    alice = await vauthors.insert({
        "name": "  Alice Smith  ",  # Will be trimmed
        "email": "ALICE@EXAMPLE.COM",  # Will be lowercased
        "bio": "Tech writer and Python enthusiast"
    })

    print(f"   Inserted via ValidatedTable:")
    print(f"     name: '{alice['name']}' (was '  Alice Smith  ')")
    print(f"     email: '{alice['email']}' (was 'ALICE@EXAMPLE.COM')")

    # Read operations work unchanged
    all_authors = await vauthors()
    print(f"\n   Read operations: {len(all_authors)} author(s) found")

    # Properties accessible
    print(f"   Table name: {vauthors.name}")
    print()

    # =========================================================================
    # Phase 16: validate_foreign_keys() - Check FK references exist
    # =========================================================================
    print("4. Phase 16: validate_foreign_keys() - FK existence checking")
    print("-" * 70)

    # Insert categories first
    cat_tech = await categories.insert({"name": "Technology", "slug": "tech"})
    cat_tutorial = await categories.insert({"name": "Tutorial", "slug": "tutorial"})

    print(f"   Created categories: {cat_tech['name']}, {cat_tutorial['name']}")

    # Test valid FK - should pass
    post_data = {
        "author_id": alice['id'],
        "category_id": cat_tech['id'],
        "title": "Hello World",
        "slug": "hello-world",
        "content": "Test content",
        "metadata": {},
        "created_at": datetime.now()
    }

    await validate_foreign_keys(db, posts, post_data)
    print(f"   Valid FK check passed for author_id={alice['id']}, category_id={cat_tech['id']}")

    # Test invalid FK - should raise ForeignKeyValidationError
    print("\n   Testing invalid FK:")
    try:
        await validate_foreign_keys(db, posts, {"author_id": 999, "category_id": 1})
    except ForeignKeyValidationError as e:
        print(f"   Caught ForeignKeyValidationError: {e.errors[0]['message']}")
    print()

    # =========================================================================
    # Phase 16: ValidatedTable with FK validation
    # =========================================================================
    print("5. Phase 16: ValidatedTable with FK validation")
    print("-" * 70)

    # Create validators for posts
    post_validators = {
        "title": validate_title,
        "slug": validate_slug,
    }

    # Wrap posts table with both field validators and FK validation
    vposts = ValidatedTable(posts, validators=post_validators, validate_fks=True)

    # Valid insert
    post1 = await vposts.insert({
        "author_id": alice['id'],
        "category_id": cat_tech['id'],
        "title": "  Getting Started with DeeBase  ",  # Will be trimmed
        "slug": "Getting Started DeeBase",  # Will be normalized
        "content": "A comprehensive guide to DeeBase...",
        "excerpt": "Learn DeeBase basics",
        "metadata": {"tags": ["python", "database"], "featured": True},
        "created_at": datetime.now()
    })

    print(f"   Inserted post via ValidatedTable:")
    print(f"     title: '{post1['title']}' (trimmed)")
    print(f"     slug: '{post1['slug']}' (normalized)")
    print(f"     author_id: {post1['author_id']} (FK validated)")

    # Invalid FK insert - blocked
    print("\n   Testing invalid FK insert:")
    try:
        await vposts.insert({
            "author_id": 999,  # Non-existent!
            "category_id": 1,
            "title": "Invalid Post",
            "slug": "invalid-post",
            "content": "This should fail",
            "metadata": {},
            "created_at": datetime.now()
        })
    except ForeignKeyValidationError as e:
        print(f"   Insert blocked: {e.errors[0]['message']}")
    print()

    # =========================================================================
    # Phase 16: ValidatedTable with xtra() filtering
    # =========================================================================
    print("6. Phase 16: ValidatedTable + xtra() filtering")
    print("-" * 70)

    # Create another author
    bob = await vauthors.insert({
        "name": "  Bob Jones  ",
        "email": "BOB@EXAMPLE.COM",
        "bio": "Software engineer and blogger"
    })

    # Add more posts
    await vposts.insert({
        "author_id": bob['id'],
        "category_id": cat_tutorial['id'],
        "title": "Advanced SQLAlchemy Patterns",
        "slug": "advanced-sqlalchemy",
        "content": "Deep dive into SQLAlchemy...",
        "metadata": {"tags": ["sqlalchemy"]},
        "published": True,
        "view_count": 150,
        "created_at": datetime.now()
    })

    # Create filtered ValidatedTable - validation still applies!
    alice_vposts = vposts.xtra(author_id=alice['id'])
    bob_vposts = vposts.xtra(author_id=bob['id'])

    print(f"   xtra() returns ValidatedTable: {type(alice_vposts).__name__}")

    alice_post_count = len(await alice_vposts())
    bob_post_count = len(await bob_vposts())
    print(f"   Alice's posts: {alice_post_count}")
    print(f"   Bob's posts: {bob_post_count}")

    # Insert through filtered ValidatedTable
    # (xtra constraints + validation + FK validation all apply)
    print()

    # =========================================================================
    # CLI Data Commands Reference
    # =========================================================================
    print("7. CLI Data Commands Reference (Phase 16)")
    print("-" * 70)
    print("""
   After running 'deebase init' and creating tables, use these commands:

   INSERT:
     deebase data insert authors -f name=Alice -f email=alice@example.com
     deebase data insert authors -j '{"name": "Bob", "email": "bob@example.com"}'
     deebase data insert authors -F authors.json  # Batch import

   LIST:
     deebase data list authors                  # Table format
     deebase data list authors --format json    # JSON format
     deebase data list authors --format csv     # CSV format
     deebase data list authors --limit 10       # Limit results

   GET:
     deebase data get authors 1                 # Get by PK
     deebase data get authors 1 --format table  # Table format

   UPDATE:
     deebase data update authors 1 -f status=inactive
     deebase data update authors 1 -j '{"name": "Alice Smith"}'

   DELETE:
     deebase data delete authors 1              # With confirmation
     deebase data delete authors 1 -y           # Skip confirmation
""")

    # =========================================================================
    # Admin Interface Reference
    # =========================================================================
    print("8. Admin Web Interface Reference (Phase 16)")
    print("-" * 70)
    print("""
   Start the admin interface with:
     deebase api init
     deebase api serve --admin

   Access the admin at:
     Dashboard:     http://127.0.0.1:8000/admin/
     Table list:    http://127.0.0.1:8000/admin/authors/
     Create form:   http://127.0.0.1:8000/admin/authors/new
     Edit form:     http://127.0.0.1:8000/admin/authors/1
     Delete:        http://127.0.0.1:8000/admin/authors/1/delete

   Features:
     - Django-like admin interface for all tables
     - FK dropdown fields populated from parent tables
     - Project validators applied automatically
     - Pagination for list views
     - Delete confirmation
""")

    # =========================================================================
    # Validators Directory Reference
    # =========================================================================
    print("9. Project Validators Directory (Phase 16)")
    print("-" * 70)
    print("""
   After 'deebase init', create validators in validators/ directory:

   validators/
   ├── __init__.py          # Validator registry
   └── authors.py           # Table-specific validators

   Example validators/authors.py:
   ```python
   def validate_email(value: str) -> str:
       if "@" not in value:
           raise ValueError("Invalid email format")
       return value.lower()

   def validate_name(value: str) -> str:
       return value.strip()

   VALIDATORS = {
       "email": validate_email,
       "name": validate_name,
   }
   ```

   Register in validators/__init__.py:
   ```python
   from . import authors

   def get_validators(table_name: str) -> dict:
       registry = {
           "authors": authors.VALIDATORS,
       }
       return registry.get(table_name, {})
   ```

   Now CLI data commands and admin will use these validators!
""")

    # =========================================================================
    # Core Features Demo (Phases 1-15)
    # =========================================================================
    print("10. Core Features Demo (Phases 1-15)")
    print("-" * 70)

    # Transactions
    print("\n   Transactions:")
    async with db.transaction():
        post1_record = await posts[post1['id']]
        post1_record['published'] = True
        post1_record['view_count'] = 100
        await posts.update(post1_record)
        print("   Published post and updated view count atomically")

    # FK Navigation
    print("\n   FK Navigation:")
    post_record = await posts[post1['id']]
    author = await posts.fk.author_id(post_record)
    category = await posts.fk.category_id(post_record)
    print(f"   Post '{post_record['title']}' by {author['name']} in [{category['name']}]")

    # Reverse navigation
    author_posts = await authors.get_children(alice, "post", "author_id")
    print(f"   {alice['name']} has {len(author_posts)} post(s)")

    # Views for JOINs
    print("\n   Views for JOINs:")
    await db.create_view(
        "post_summaries",
        """
        SELECT p.id, p.title, p.view_count, p.published,
               a.name as author_name, c.name as category_name
        FROM post p
        JOIN author a ON p.author_id = a.id
        JOIN category c ON p.category_id = c.id
        """
    )
    summaries = await db.v.post_summaries()
    print(f"   Post summaries view: {len(summaries)} rows")
    for s in summaries:
        pub = "published" if s['published'] else "draft"
        print(f"     '{s['title']}' by {s['author_name']} ({pub})")

    # Error handling
    print("\n   Error handling:")
    try:
        await posts[999]
    except NotFoundError as e:
        print(f"   NotFoundError: Record not found in {e.table_name}")

    print()

    # =========================================================================
    # Cleanup
    # =========================================================================
    print("11. Cleanup")
    print("-" * 70)
    await db.v.post_summaries.drop()
    await comments.drop()
    await posts.drop()
    await categories.drop()
    await authors.drop()
    await db.close()
    print("   Dropped all tables and views")
    print("   Database closed")
    print()

    print("=" * 70)
    print("Complete example finished successfully!")
    print("Phase 16 features demonstrated: validation layer, CLI commands, admin")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
