"""Pytest configuration and fixtures for deebase tests."""

import pytest
import pytest_asyncio
from sqlalchemy import text

from deebase import Database


@pytest_asyncio.fixture
async def db():
    """Create an in-memory SQLite database for testing.

    Yields:
        Database instance connected to in-memory SQLite
    """
    database = Database("sqlite+aiosqlite:///:memory:")
    yield database
    await database.close()


@pytest_asyncio.fixture
async def db_with_sample_table(db):
    """Create a database with a sample users table.

    Args:
        db: Database fixture

    Yields:
        Database with users table created
    """
    # Create a simple users table
    await db.q("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            age INTEGER
        )
    """)

    # Insert some sample data
    await db.q("""
        INSERT INTO users (name, email, age) VALUES
        ('Alice', 'alice@example.com', 30),
        ('Bob', 'bob@example.com', 25),
        ('Charlie', 'charlie@example.com', 35)
    """)

    yield db


@pytest.fixture
def sample_user_class():
    """Sample User class for table creation tests."""
    class User:
        id: int
        name: str
        email: str
        age: int

    return User
