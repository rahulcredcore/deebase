"""
Example: Transaction Support

This example demonstrates DeeBase's transaction support for multi-operation
database transactions. Transactions ensure atomicity - all operations succeed
together or fail together.

Features demonstrated:
- Basic transaction usage with db.transaction()
- Automatic commit on success
- Automatic rollback on exception
- Mixed CRUD operations in transactions
- Read-modify-write patterns
- Error handling and rollback scenarios
- Consistent reads within transactions
"""

import asyncio
from deebase import Database, NotFoundError, IntegrityError


async def main():
    print("=" * 70)
    print("Transaction Support Example")
    print("=" * 70)
    print()

    # Create in-memory database
    db = Database("sqlite+aiosqlite:///:memory:")

    # =========================================================================
    # 1. Basic Transaction Usage
    # =========================================================================
    print("1. Basic Transaction Usage")
    print("-" * 70)

    class User:
        id: int
        name: str
        email: str
        balance: float

    users = await db.create(User, pk='id')
    print(f"✓ Created table: {users._name}")
    print()

    # Without transaction - each operation auto-commits
    print("Without transaction (auto-commit per operation):")
    await users.insert({"name": "Alice", "email": "alice@example.com", "balance": 100.0})
    await users.insert({"name": "Bob", "email": "bob@example.com", "balance": 50.0})
    print("  ✓ Inserted Alice and Bob (2 separate commits)")
    print()

    # With transaction - all operations commit together
    print("With transaction (atomic multi-operation):")
    async with db.transaction():
        await users.insert({"name": "Charlie", "email": "charlie@example.com", "balance": 75.0})
        await users.insert({"name": "Diana", "email": "diana@example.com", "balance": 150.0})
        print("  ✓ Inserted Charlie and Diana (1 atomic commit)")
    print()

    all_users = await users()
    print(f"Total users: {len(all_users)}")
    print()

    # =========================================================================
    # 2. Automatic Rollback on Exception
    # =========================================================================
    print("\n2. Automatic Rollback on Exception")
    print("-" * 70)

    print("Attempting transaction that will fail:")
    initial_count = len(await users())

    try:
        async with db.transaction():
            await users.insert({"name": "Eve", "email": "eve@example.com", "balance": 200.0})
            print("  • Inserted Eve")
            await users.insert({"name": "Frank", "email": "frank@example.com", "balance": 300.0})
            print("  • Inserted Frank")
            # Simulate an error
            raise RuntimeError("Simulated transaction failure!")
    except RuntimeError as e:
        print(f"  ✗ Transaction failed: {e}")
    print()

    final_count = len(await users())
    print(f"Users before transaction: {initial_count}")
    print(f"Users after rollback: {final_count}")
    print(f"✓ Rollback successful - Eve and Frank not committed")
    print()

    # =========================================================================
    # 3. Money Transfer (Read-Modify-Write Pattern)
    # =========================================================================
    print("\n3. Money Transfer Example (Read-Modify-Write)")
    print("-" * 70)

    # Get Alice and Bob
    alice = await users.lookup(name="Alice")
    bob = await users.lookup(name="Bob")

    print(f"Before transfer:")
    print(f"  • Alice: ${alice['balance']:.2f}")
    print(f"  • Bob: ${bob['balance']:.2f}")
    print()

    # Transfer $30 from Alice to Bob
    transfer_amount = 30.0

    async with db.transaction():
        # Read current balances
        alice = await users[alice['id']]
        bob = await users[bob['id']]

        # Modify balances
        alice['balance'] -= transfer_amount
        bob['balance'] += transfer_amount

        # Write updates
        await users.update(alice)
        await users.update(bob)
        print(f"✓ Transferred ${transfer_amount:.2f} from Alice to Bob")
    print()

    # Verify final balances
    alice = await users.lookup(name="Alice")
    bob = await users.lookup(name="Bob")
    print(f"After transfer:")
    print(f"  • Alice: ${alice['balance']:.2f}")
    print(f"  • Bob: ${bob['balance']:.2f}")
    print()

    # =========================================================================
    # 4. Failed Transfer (Insufficient Funds)
    # =========================================================================
    print("\n4. Failed Transfer Example (Rollback on Business Logic Error)")
    print("-" * 70)

    print("Attempting to transfer $200 from Bob (balance: $80):")

    try:
        async with db.transaction():
            bob = await users.lookup(name="Bob")
            charlie = await users.lookup(name="Charlie")

            transfer_amount = 200.0

            # Check sufficient funds
            if bob['balance'] < transfer_amount:
                raise ValueError(f"Insufficient funds: ${bob['balance']:.2f} < ${transfer_amount:.2f}")

            # This code won't execute due to exception
            bob['balance'] -= transfer_amount
            charlie['balance'] += transfer_amount
            await users.update(bob)
            await users.update(charlie)
    except ValueError as e:
        print(f"  ✗ Transfer failed: {e}")
    print()

    # Verify balances unchanged
    bob_after = await users.lookup(name="Bob")
    print(f"Bob's balance after failed transfer: ${bob_after['balance']:.2f}")
    print("✓ Rollback successful - balances unchanged")
    print()

    # =========================================================================
    # 5. Batch Operations
    # =========================================================================
    print("\n5. Batch Operations in Transaction")
    print("-" * 70)

    class Transaction:
        id: int
        user_id: int
        amount: float
        description: str

    transactions = await db.create(Transaction, pk='id')
    print(f"✓ Created table: {transactions._name}")
    print()

    print("Recording multiple transactions atomically:")
    async with db.transaction():
        await transactions.insert({
            "user_id": alice['id'],
            "amount": -30.0,
            "description": "Transfer to Bob"
        })
        await transactions.insert({
            "user_id": bob['id'],
            "amount": 30.0,
            "description": "Transfer from Alice"
        })
        await transactions.insert({
            "user_id": alice['id'],
            "amount": -10.0,
            "description": "Service fee"
        })
        print("  ✓ Recorded 3 transactions atomically")
    print()

    all_txns = await transactions()
    print(f"Total transactions recorded: {len(all_txns)}")
    print()

    # =========================================================================
    # 6. Constraint Violation Rollback
    # =========================================================================
    print("\n6. Automatic Rollback on Constraint Violation")
    print("-" * 70)

    print("Attempting to insert duplicate user IDs:")
    initial_user_count = len(await users())

    try:
        async with db.transaction():
            await users.insert({"id": 100, "name": "George", "email": "george@example.com", "balance": 100.0})
            print("  • Inserted George (id=100)")
            await users.insert({"id": 100, "name": "Hannah", "email": "hannah@example.com", "balance": 50.0})
            print("  • Attempting to insert Hannah with same ID...")
    except IntegrityError as e:
        print(f"  ✗ IntegrityError: {e}")
    print()

    final_user_count = len(await users())
    print(f"Users before: {initial_user_count}")
    print(f"Users after: {final_user_count}")
    print("✓ Rollback successful - George not committed due to Hannah's constraint violation")
    print()

    # =========================================================================
    # 7. Mixed Operations (CRUD)
    # =========================================================================
    print("\n7. Mixed CRUD Operations in Transaction")
    print("-" * 70)

    print("Performing complex multi-step operation:")
    async with db.transaction():
        # Create new user
        new_user = await users.insert({
            "name": "Isabel",
            "email": "isabel@example.com",
            "balance": 500.0
        })
        print(f"  • Created user: {new_user['name']}")

        # Read existing user
        diana = await users.lookup(name="Diana")
        print(f"  • Found user: {diana['name']}")

        # Update
        diana['balance'] += 50.0
        await users.update(diana)
        print(f"  • Updated {diana['name']}'s balance to ${diana['balance']:.2f}")

        # Delete
        charlie = await users.lookup(name="Charlie")
        await users.delete(charlie['id'])
        print(f"  • Deleted user: Charlie")

        # Record transaction
        await transactions.insert({
            "user_id": diana['id'],
            "amount": 50.0,
            "description": "Bonus payment"
        })
        print("  • Recorded transaction")
    print()
    print("✓ All operations committed atomically")
    print()

    # =========================================================================
    # 8. Operations Outside Transactions Still Work
    # =========================================================================
    print("\n8. Non-Transactional Operations (Backward Compatibility)")
    print("-" * 70)

    print("Operations without db.transaction() still auto-commit:")
    standalone_user = await users.insert({
        "name": "Jack",
        "email": "jack@example.com",
        "balance": 250.0
    })
    print(f"  ✓ Inserted {standalone_user['name']} (auto-committed)")
    print()

    standalone_user['balance'] = 300.0
    await users.update(standalone_user)
    print(f"  ✓ Updated {standalone_user['name']}'s balance (auto-committed)")
    print()

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 70)
    print("Transaction Support Summary")
    print("=" * 70)
    print()
    print("✅ Key Features:")
    print("  • Atomic multi-operation transactions")
    print("  • Automatic commit on success")
    print("  • Automatic rollback on any exception")
    print("  • Consistent reads within transactions")
    print("  • Works with all CRUD operations")
    print("  • Backward compatible (non-transactional ops still work)")
    print()
    print("💡 Use Transactions For:")
    print("  • Money transfers and financial operations")
    print("  • Multi-table updates that must stay consistent")
    print("  • Batch operations that should succeed/fail together")
    print("  • Complex business logic requiring atomicity")
    print()
    print("📊 Final Statistics:")
    final_users = await users()
    final_txns = await transactions()
    print(f"  • Total users: {len(final_users)}")
    print(f"  • Total transactions: {len(final_txns)}")
    print()

    # Clean up
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
