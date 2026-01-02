#!/usr/bin/env python3
"""Phase 13: Command-Line Interface (CLI) Example.

This file demonstrates the DeeBase CLI commands. Since CLI commands
are run from the terminal, this file shows the equivalent Python code
for reference.

CLI COMMANDS OVERVIEW
=====================

To use the CLI, run: deebase <command> [options]

INITIALIZATION
--------------
# Initialize a new project (standalone)
$ deebase init

# Initialize with existing package
$ deebase init --package myapp

# Initialize with new package
$ deebase init --new-package myapp

# Initialize for PostgreSQL
$ deebase init --postgres

TABLE MANAGEMENT
----------------
# Create table with fields
$ deebase table create users \\
    id:int \\
    name:str \\
    email:str:unique \\
    bio:Text:nullable \\
    status:str:default=active \\
    --pk id

# Create table with foreign key
$ deebase table create posts \\
    id:int \\
    author_id:int:fk=users \\
    title:str \\
    content:Text \\
    views:int:default=0 \\
    --pk id \\
    --index author_id

# List all tables
$ deebase table list

# Show table schema
$ deebase table schema users

# Drop a table
$ deebase table drop old_table --yes

INDEX MANAGEMENT
----------------
# Create simple index
$ deebase index create posts title

# Create composite index
$ deebase index create posts author_id,created_at

# Create unique index
$ deebase index create users email --unique --name ix_users_email

# List indexes on table
$ deebase index list posts

# Drop index
$ deebase index drop ix_old_index --yes

VIEW MANAGEMENT
---------------
# Create view from SQL
$ deebase view create active_users --sql "SELECT * FROM users WHERE status = 'active'"

# Create view with join
$ deebase view create user_posts --sql "SELECT u.name, p.title FROM users u JOIN posts p ON u.id = p.author_id"

# Replace existing view
$ deebase view create active_users --sql "SELECT * FROM users WHERE active = 1" --replace

# List views
$ deebase view list

# Drop view
$ deebase view drop old_view --yes

DATABASE OPERATIONS
-------------------
# Show database info
$ deebase db info

# Execute raw SQL (recorded in migration)
$ deebase sql "CREATE INDEX ix_custom ON users(name)"

# Execute raw SQL (not recorded)
$ deebase sql "SELECT COUNT(*) FROM users" --no-record

# Interactive SQL shell
$ deebase db shell

CODE GENERATION
---------------
# Generate models from all tables
$ deebase codegen

# Generate models from specific tables
$ deebase codegen users posts

# Generate to custom output path
$ deebase codegen --output src/myapp/models.py

MIGRATIONS
----------
# Show migration status
$ deebase migrate status

# Seal current migration (freeze it, start new one)
$ deebase migrate seal "initial schema"

# Create new empty migration
$ deebase migrate new "add comments table"
"""

import asyncio
import tempfile
import os
from pathlib import Path

# This example demonstrates what the CLI does under the hood.
# The CLI commands generate and execute code like this:


async def demonstrate_cli_equivalent():
    """Demonstrate what CLI commands do internally."""
    from deebase import Database, Text, ForeignKey, Index

    # Create a temporary directory for our demo
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "app.db")
        db = Database(f"sqlite+aiosqlite:///{db_path}")

        print("=" * 60)
        print("DeeBase CLI - Python Equivalent Demo")
        print("=" * 60)

        # ----------------------------------------------------------------
        # What `deebase table create users id:int name:str email:str:unique --pk id` does:
        # ----------------------------------------------------------------
        print("\n1. Creating 'users' table (equivalent to CLI command)...")

        class User:
            id: int
            name: str
            email: str
            status: str = "active"

        users = await db.create(
            User,
            pk='id',
            indexes=[Index('ix_user_email', 'email', unique=True)]
        )
        print(f"   Created table: {users._name}")
        print(f"   Schema:\n{users.schema}")

        # ----------------------------------------------------------------
        # What `deebase table create posts id:int author_id:int:fk=users title:str --pk id --index author_id` does:
        # ----------------------------------------------------------------
        print("\n2. Creating 'posts' table with FK...")

        class Post:
            id: int
            author_id: ForeignKey[int, "user"]
            title: str
            content: Text
            views: int = 0

        posts = await db.create(
            Post,
            pk='id',
            indexes=['author_id']
        )
        print(f"   Created table: {posts._name}")

        # ----------------------------------------------------------------
        # What `deebase table list` does:
        # ----------------------------------------------------------------
        print("\n3. Listing tables...")
        await db.reflect()
        print(f"   Tables: user, post")

        # ----------------------------------------------------------------
        # Insert some data for demonstration
        # ----------------------------------------------------------------
        print("\n4. Inserting sample data...")
        alice = await users.insert({"name": "Alice", "email": "alice@example.com"})
        bob = await users.insert({"name": "Bob", "email": "bob@example.com"})
        print(f"   Inserted users: Alice (id={alice['id']}), Bob (id={bob['id']})")

        post1 = await posts.insert({"author_id": alice['id'], "title": "Hello World", "content": "First post!"})
        post2 = await posts.insert({"author_id": alice['id'], "title": "Second Post", "content": "More content"})
        print(f"   Inserted posts: {post1['title']}, {post2['title']}")

        # ----------------------------------------------------------------
        # What `deebase view create active_users --sql "..."` does:
        # ----------------------------------------------------------------
        print("\n5. Creating view...")
        view = await db.create_view(
            "active_users",
            "SELECT * FROM user WHERE status = 'active'"
        )
        print(f"   Created view: active_users")

        active = await view()
        print(f"   Active users: {len(active)}")

        # ----------------------------------------------------------------
        # What `deebase index create posts title` does:
        # ----------------------------------------------------------------
        print("\n6. Creating additional index...")
        await posts.create_index("title", name="ix_post_title")
        print(f"   Created index: ix_post_title on posts(title)")

        # ----------------------------------------------------------------
        # What `deebase index list posts` does:
        # ----------------------------------------------------------------
        print("\n7. Listing indexes on 'posts'...")
        for idx in posts.indexes:
            unique = "UNIQUE " if idx.get('unique') else ""
            cols = ', '.join(idx.get('columns', []))
            print(f"   {idx['name']}: {unique}({cols})")

        # ----------------------------------------------------------------
        # What `deebase sql "SELECT COUNT(*) FROM users"` does:
        # ----------------------------------------------------------------
        print("\n8. Executing raw SQL...")
        result = await db.q("SELECT COUNT(*) as user_count FROM user")
        print(f"   User count: {result[0]['user_count']}")

        # ----------------------------------------------------------------
        # What `deebase codegen` does (generates code like this):
        # ----------------------------------------------------------------
        print("\n9. Code generation output (what deebase codegen produces):")
        print('   """Auto-generated database models."""')
        print('   from dataclasses import dataclass')
        print('   from typing import Optional')
        print('')
        print('   @dataclass')
        print('   class User:')
        print('       id: Optional[int] = None')
        print('       name: Optional[str] = None')
        print('       email: Optional[str] = None')
        print('       status: Optional[str] = None')

        # ----------------------------------------------------------------
        # What `deebase db info` shows:
        # ----------------------------------------------------------------
        print("\n10. Database info:")
        print(f"    Database: SQLite ({db_path})")
        print(f"    Tables: user, post")
        print(f"    Views: active_users")

        await db.close()

        print("\n" + "=" * 60)
        print("Demo complete!")
        print("=" * 60)
        print("\nTo use the actual CLI, run these commands in your terminal:")
        print("  deebase init")
        print("  deebase table create users id:int name:str email:str:unique --pk id")
        print("  deebase table list")
        print("  deebase migrate status")


if __name__ == "__main__":
    asyncio.run(demonstrate_cli_equivalent())
