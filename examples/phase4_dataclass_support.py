"""
Phase 4 Example: Dataclass Support

This example demonstrates Phase 4 dataclass features:
- Generating dataclasses from table metadata with .dataclass()
- CRUD operations with dataclass instances
- Using actual @dataclass decorated classes
- Mixing dict and dataclass inputs
- Type-safe database operations
"""

import asyncio
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from deebase import Database, Text


async def main():
    print("=" * 70)
    print("Phase 4: Dataclass Support")
    print("=" * 70)
    print()

    # Create in-memory database
    db = Database("sqlite+aiosqlite:///:memory:")

    # =========================================================================
    # 1. Generated Dataclasses with .dataclass()
    # =========================================================================
    print("1. Generated Dataclasses")
    print("-" * 70)

    # Define a simple class with type annotations (not a @dataclass)
    class Cat:
        id: int
        name: str
        breed: str
        weight: float

    cats = await db.create(Cat, pk='id')
    print(f"✓ Created table: {cats._name}")

    # By default, operations return dicts
    print("\nBefore calling .dataclass() - returns dicts:")
    tom_dict = await cats.insert({"name": "Tom", "breed": "Tabby", "weight": 10.2})
    print(f"  • Type: {type(tom_dict)}")
    print(f"  • Value: {tom_dict}")

    # Call .dataclass() to enable dataclass mode
    print("\nCalling .dataclass() to generate dataclass:")
    CatDC = cats.dataclass()
    print(f"  • Generated: {CatDC}")
    print(f"  • Fields: {', '.join(f.name for f in CatDC.__dataclass_fields__.values())}")

    # Now operations return dataclass instances
    print("\nAfter calling .dataclass() - returns dataclass instances:")
    fluffy = await cats.insert({"name": "Fluffy", "breed": "Persian", "weight": 8.5})
    print(f"  • Type: {type(fluffy)}")
    print(f"  • Value: {fluffy}")
    print(f"  • Access fields: {fluffy.name}, {fluffy.breed}, {fluffy.weight}kg")
    print()

    # =========================================================================
    # 2. CRUD Operations with Dataclass Instances
    # =========================================================================
    print("\n2. CRUD Operations with Dataclass Instances")
    print("-" * 70)

    # INSERT with dataclass instance
    print("INSERT with dataclass instance:")
    whiskers = await cats.insert(CatDC(id=None, name="Whiskers", breed="Siamese", weight=9.0))
    print(f"  • Inserted: {whiskers}")
    print()

    # SELECT returns dataclass instances
    print("SELECT all cats:")
    all_cats = await cats()
    for cat in all_cats:
        print(f"  • {cat.name} ({cat.breed}): {cat.weight}kg")
    print()

    # GET by PK returns dataclass
    print(f"GET by PK ({fluffy.id}):")
    found = await cats[fluffy.id]
    print(f"  • Found: {found}")
    print()

    # LOOKUP returns dataclass
    print("LOOKUP by breed:")
    siamese = await cats.lookup(breed="Siamese")
    print(f"  • Found: {siamese}")
    print()

    # UPDATE with dataclass instance
    print("UPDATE with dataclass instance:")
    whiskers.weight = 9.5  # Cat gained weight!
    updated = await cats.update(whiskers)
    print(f"  • Updated: {updated}")
    print(f"  • New weight: {updated.weight}kg")
    print()

    # DELETE still works with PK value
    print("DELETE by PK:")
    await cats.delete(tom_dict['id'])
    remaining = await cats()
    print(f"  • Remaining cats: {len(remaining)}")
    print()

    # =========================================================================
    # 3. Using Actual @dataclass Decorated Classes
    # =========================================================================
    print("\n3. Using Actual @dataclass Decorated Classes")
    print("-" * 70)

    @dataclass
    class Dog:
        id: Optional[int] = None
        name: str = ""
        breed: str = ""
        age: int = 0

    dogs = await db.create(Dog, pk='id')
    print(f"✓ Created table from @dataclass: {dogs._name}")
    print()

    # Insert with @dataclass instance
    print("INSERT with @dataclass instance:")
    buddy = await dogs.insert(Dog(name="Buddy", breed="Golden Retriever", age=3))
    print(f"  • Inserted: {buddy}")
    print(f"  • Type: {type(buddy)}")
    print(f"  • Is Dog: {isinstance(buddy, Dog)}")
    print()

    # All operations automatically use the @dataclass
    print("INSERT another dog:")
    max_dog = await dogs.insert(Dog(name="Max", breed="Labrador", age=5))
    print(f"  • Inserted: {max_dog}")
    print()

    print("SELECT all dogs:")
    all_dogs = await dogs()
    for dog in all_dogs:
        print(f"  • {dog.name} ({dog.breed}): {dog.age} years old")
    print()

    # =========================================================================
    # 4. Mixing Dict and Dataclass Inputs
    # =========================================================================
    print("\n4. Mixing Dict and Dataclass Inputs")
    print("-" * 70)

    class Bird:
        id: int
        species: str
        color: str

    birds = await db.create(Bird, pk='id')
    BirdDC = birds.dataclass()
    print(f"✓ Created table: {birds._name}")
    print()

    # Insert with dict
    print("INSERT with dict:")
    robin = await birds.insert({"species": "Robin", "color": "Red"})
    print(f"  • Result: {robin}")
    print(f"  • Type: {type(robin).__name__}")
    print()

    # Insert with dataclass
    print("INSERT with dataclass:")
    blue_jay = await birds.insert(BirdDC(id=None, species="Blue Jay", color="Blue"))
    print(f"  • Result: {blue_jay}")
    print(f"  • Type: {type(blue_jay).__name__}")
    print()

    # Update with dict works
    print("UPDATE with dict:")
    updated_robin = await birds.update({"id": robin.id, "species": "Robin", "color": "Orange-Red"})
    print(f"  • Result: {updated_robin}")
    print()

    # Update with dataclass works
    print("UPDATE with dataclass:")
    blue_jay.color = "Bright Blue"
    updated_jay = await birds.update(blue_jay)
    print(f"  • Result: {updated_jay}")
    print()

    # =========================================================================
    # 5. Dataclasses with Rich Types
    # =========================================================================
    print("\n5. Dataclasses with Rich Types")
    print("-" * 70)

    class Book:
        id: int
        title: str
        author: str
        summary: Text              # TEXT (unlimited)
        metadata: dict             # JSON
        published: datetime        # TIMESTAMP

    books = await db.create(Book, pk='id')
    BookDC = books.dataclass()
    print(f"✓ Created table: {books._name}")
    print()

    # Insert with rich types using dataclass
    print("INSERT with rich types:")
    book = await books.insert(BookDC(
        id=None,
        title="The Python Guide",
        author="Alice Smith",
        summary="A" * 500,  # Long text
        metadata={"pages": 250, "isbn": "123-456", "tags": ["programming", "python"]},
        published=datetime(2025, 1, 1, 10, 0, 0)
    ))
    print(f"  • Title: {book.title}")
    print(f"  • Author: {book.author}")
    print(f"  • Summary length: {len(book.summary)} chars")
    print(f"  • Metadata: {book.metadata}")
    print(f"  • Published: {book.published}")
    print()

    # =========================================================================
    # 6. Type Safety Benefits
    # =========================================================================
    print("\n6. Type Safety Benefits")
    print("-" * 70)

    print("With dataclasses, you get:")
    print("  • IDE autocomplete for fields")
    print("  • Type checking with mypy/pyright")
    print("  • Clear data structures")
    print("  • Runtime validation")
    print()

    # Example: IDE knows about fields
    all_cats = await cats()
    for cat in all_cats:
        # IDE autocomplete works here!
        print(f"  • {cat.name.upper()}: {cat.weight:.1f}kg")
    print()

    # Clean up
    await db.close()

    print("\n" + "=" * 70)
    print("Phase 4 Dataclass Support - Complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
