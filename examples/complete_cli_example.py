#!/usr/bin/env python3
"""Complete CLI Example: Building a Blog with DeeBase CLI.

This example demonstrates using the DeeBase CLI to build a complete
blog application from scratch. It runs actual CLI commands in a
temporary directory, showing the real workflow.

Run with: uv run examples/complete_cli_example.py
"""

import subprocess
import tempfile
import os
import sys
from pathlib import Path


def run_cmd(cmd: str, cwd: str, check: bool = True) -> str:
    """Run a CLI command and return output."""
    # Use uv run to ensure we use the project's deebase
    full_cmd = f"uv run deebase {cmd}"
    result = subprocess.run(
        full_cmd,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        print(f"Command failed: {full_cmd}")
        print(f"stderr: {result.stderr}")
        print(f"stdout: {result.stdout}")
        sys.exit(1)
    return result.stdout + result.stderr


def main():
    print("=" * 70)
    print("DeeBase CLI Complete Example: Building a Blog")
    print("=" * 70)

    # Create a temporary directory for our project
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"\nWorking in: {tmpdir}\n")

        # ================================================================
        # STEP 1: Initialize the project
        # ================================================================
        print("STEP 1: Initialize DeeBase Project")
        print("-" * 50)
        print("$ deebase init")
        output = run_cmd("init", tmpdir)
        print(output)

        # Show what was created
        print("Project structure created:")
        for item in sorted(Path(tmpdir).rglob("*")):
            rel = item.relative_to(tmpdir)
            prefix = "  " * (len(rel.parts) - 1)
            print(f"  {prefix}{item.name}{'/' if item.is_dir() else ''}")

        # ================================================================
        # STEP 2: Create the Users table
        # ================================================================
        print("\n" + "=" * 70)
        print("STEP 2: Create Users Table")
        print("-" * 50)
        cmd = 'table create users id:int name:str email:str:unique bio:Text:nullable status:str:default=active --pk id'
        print(f"$ deebase {cmd}")
        output = run_cmd(cmd, tmpdir)
        print(output)

        # ================================================================
        # STEP 3: Create the Posts table with FK
        # ================================================================
        print("\n" + "=" * 70)
        print("STEP 3: Create Posts Table (with Foreign Key)")
        print("-" * 50)
        cmd = 'table create posts id:int author_id:int:fk=users title:str content:Text views:int:default=0 --pk id --index author_id'
        print(f"$ deebase {cmd}")
        output = run_cmd(cmd, tmpdir)
        print(output)

        # ================================================================
        # STEP 4: Create the Comments table
        # ================================================================
        print("\n" + "=" * 70)
        print("STEP 4: Create Comments Table")
        print("-" * 50)
        cmd = 'table create comments id:int post_id:int:fk=posts user_id:int:fk=users content:Text --pk id'
        print(f"$ deebase {cmd}")
        output = run_cmd(cmd, tmpdir)
        print(output)

        # ================================================================
        # STEP 5: List all tables
        # ================================================================
        print("\n" + "=" * 70)
        print("STEP 5: List All Tables")
        print("-" * 50)
        print("$ deebase table list")
        output = run_cmd("table list", tmpdir)
        print(output)

        # ================================================================
        # STEP 6: Show table schemas
        # ================================================================
        print("\n" + "=" * 70)
        print("STEP 6: Show Table Schemas")
        print("-" * 50)
        for table in ["users", "posts", "comments"]:
            print(f"$ deebase table schema {table}")
            output = run_cmd(f"table schema {table}", tmpdir)
            print(output)

        # ================================================================
        # STEP 7: Create additional indexes
        # ================================================================
        print("\n" + "=" * 70)
        print("STEP 7: Create Additional Indexes")
        print("-" * 50)

        print("$ deebase index create posts title --name ix_posts_title")
        output = run_cmd("index create posts title --name ix_posts_title", tmpdir)
        print(output)

        print("$ deebase index create comments post_id,user_id --name ix_comments_post_user")
        output = run_cmd("index create comments post_id,user_id --name ix_comments_post_user", tmpdir)
        print(output)

        # ================================================================
        # STEP 8: List indexes
        # ================================================================
        print("\n" + "=" * 70)
        print("STEP 8: List Indexes on Posts")
        print("-" * 50)
        print("$ deebase index list posts")
        output = run_cmd("index list posts", tmpdir)
        print(output)

        # ================================================================
        # STEP 9: Create views
        # ================================================================
        print("\n" + "=" * 70)
        print("STEP 9: Create Views")
        print("-" * 50)

        # Active users view
        print('$ deebase view create active_users --sql "SELECT * FROM users WHERE status = \'active\'"')
        output = run_cmd('view create active_users --sql "SELECT * FROM users WHERE status = \'active\'"', tmpdir)
        print(output)

        # Posts with authors view (JOIN)
        sql = "SELECT p.id, p.title, p.views, u.name as author FROM posts p JOIN users u ON p.author_id = u.id"
        print(f'$ deebase view create posts_with_authors --sql "{sql}"')
        output = run_cmd(f'view create posts_with_authors --sql "{sql}"', tmpdir)
        print(output)

        # ================================================================
        # STEP 10: List views
        # ================================================================
        print("\n" + "=" * 70)
        print("STEP 10: List Views")
        print("-" * 50)
        print("$ deebase view list")
        output = run_cmd("view list", tmpdir)
        print(output)

        # ================================================================
        # STEP 11: Insert sample data via SQL
        # ================================================================
        print("\n" + "=" * 70)
        print("STEP 11: Insert Sample Data")
        print("-" * 50)

        # Insert users
        print("$ deebase sql \"INSERT INTO users (name, email) VALUES ('Alice', 'alice@example.com')\" --no-record")
        run_cmd("sql \"INSERT INTO users (name, email) VALUES ('Alice', 'alice@example.com')\" --no-record", tmpdir)

        print("$ deebase sql \"INSERT INTO users (name, email) VALUES ('Bob', 'bob@example.com')\" --no-record")
        run_cmd("sql \"INSERT INTO users (name, email) VALUES ('Bob', 'bob@example.com')\" --no-record", tmpdir)
        print("Users inserted.")

        # Insert posts
        print("$ deebase sql \"INSERT INTO posts (author_id, title, content, views) VALUES (1, 'Hello World', 'My first post!', 100)\" --no-record")
        run_cmd("sql \"INSERT INTO posts (author_id, title, content, views) VALUES (1, 'Hello World', 'My first post!', 100)\" --no-record", tmpdir)

        print("$ deebase sql \"INSERT INTO posts (author_id, title, content, views) VALUES (1, 'Second Post', 'More content here', 50)\" --no-record")
        run_cmd("sql \"INSERT INTO posts (author_id, title, content, views) VALUES (1, 'Second Post', 'More content here', 50)\" --no-record", tmpdir)

        print("$ deebase sql \"INSERT INTO posts (author_id, title, content, views) VALUES (2, 'Bobs Post', 'Bob writes too', 25)\" --no-record")
        run_cmd("sql \"INSERT INTO posts (author_id, title, content, views) VALUES (2, 'Bobs Post', 'Bob writes too', 25)\" --no-record", tmpdir)
        print("Posts inserted.")

        # Insert comments
        print("$ deebase sql \"INSERT INTO comments (post_id, user_id, content) VALUES (1, 2, 'Great post!')\" --no-record")
        run_cmd("sql \"INSERT INTO comments (post_id, user_id, content) VALUES (1, 2, 'Great post!')\" --no-record", tmpdir)
        print("Comments inserted.")

        # ================================================================
        # STEP 12: Query data
        # ================================================================
        print("\n" + "=" * 70)
        print("STEP 12: Query Data")
        print("-" * 50)

        print("$ deebase sql \"SELECT * FROM users\" --no-record")
        output = run_cmd("sql \"SELECT * FROM users\" --no-record", tmpdir)
        print(output)

        print("$ deebase sql \"SELECT * FROM posts_with_authors\" --no-record")
        output = run_cmd("sql \"SELECT * FROM posts_with_authors\" --no-record", tmpdir)
        print(output)

        # ================================================================
        # STEP 13: Database info
        # ================================================================
        print("\n" + "=" * 70)
        print("STEP 13: Database Info")
        print("-" * 50)
        print("$ deebase db info")
        output = run_cmd("db info", tmpdir)
        print(output)

        # ================================================================
        # STEP 14: Generate models
        # ================================================================
        print("\n" + "=" * 70)
        print("STEP 14: Generate Python Models")
        print("-" * 50)
        print("$ deebase codegen")
        output = run_cmd("codegen", tmpdir)
        print(output)

        # Show generated models
        models_path = Path(tmpdir) / "models" / "models.py"
        if models_path.exists():
            print("Generated models.py:")
            print("-" * 30)
            print(models_path.read_text())

        # ================================================================
        # STEP 15: Migration status
        # ================================================================
        print("\n" + "=" * 70)
        print("STEP 15: Check Migration Status")
        print("-" * 50)
        print("$ deebase migrate status")
        output = run_cmd("migrate status", tmpdir)
        print(output)

        # Show current migration file
        migrations_dir = Path(tmpdir) / "migrations"
        for mig_file in migrations_dir.glob("*.py"):
            print(f"\nMigration file: {mig_file.name}")
            print("-" * 30)
            content = mig_file.read_text()
            # Show first 50 lines
            lines = content.split('\n')[:50]
            print('\n'.join(lines))
            if len(content.split('\n')) > 50:
                print("... (truncated)")

        # ================================================================
        # STEP 16: Seal migration
        # ================================================================
        print("\n" + "=" * 70)
        print("STEP 16: Seal Migration (freeze current, start new)")
        print("-" * 50)
        print('$ deebase migrate seal "initial blog schema"')
        output = run_cmd('migrate seal "initial blog schema"', tmpdir)
        print(output)

        # Show new migration status
        print("\n$ deebase migrate status")
        output = run_cmd("migrate status", tmpdir)
        print(output)

        # List migration files
        print("\nMigration files:")
        for mig_file in sorted(migrations_dir.glob("*.py")):
            print(f"  {mig_file.name}")

        # ================================================================
        # STEP 17: Add more schema changes
        # ================================================================
        print("\n" + "=" * 70)
        print("STEP 17: Add More Schema Changes")
        print("-" * 50)

        # Add tags table
        print("$ deebase table create tags id:int name:str:unique --pk id")
        output = run_cmd("table create tags id:int name:str:unique --pk id", tmpdir)
        print(output)

        # Add post_tags junction table
        print("$ deebase table create post_tags post_id:int:fk=posts tag_id:int:fk=tags --pk post_id,tag_id")
        output = run_cmd("table create post_tags post_id:int:fk=posts tag_id:int:fk=tags --pk post_id,tag_id", tmpdir)
        print(output)

        # Check migration status again
        print("\n$ deebase migrate status")
        output = run_cmd("migrate status", tmpdir)
        print(output)

        # ================================================================
        # SUMMARY
        # ================================================================
        print("\n" + "=" * 70)
        print("SUMMARY: What We Built")
        print("=" * 70)
        print("""
Tables created:
  - users (id, name, email, bio, status)
  - posts (id, author_id -> users, title, content, views)
  - comments (id, post_id -> posts, user_id -> users, content)
  - tags (id, name)
  - post_tags (post_id -> posts, tag_id -> tags)

Views created:
  - active_users: Users with status='active'
  - posts_with_authors: Posts joined with author names

Indexes created:
  - ix_posts_author_id on posts(author_id)
  - ix_posts_title on posts(title)
  - ix_comments_post_user on comments(post_id, user_id)

Migrations:
  - 001_initial_blog_schema.py (sealed)
  - 002_*.py (current, unsealed)

Generated:
  - models/models.py with Python dataclasses
""")

        print("CLI workflow complete!")
        print("=" * 70)


if __name__ == "__main__":
    main()
