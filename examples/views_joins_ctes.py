"""
DeeBase Example: Views for Joins and CTEs

This example demonstrates how to use views as an elegant solution for
JOIN queries without needing a dedicated join API. Views, JOINs, and CTEs
all produce result sets with column metadata - DeeBase's reflect_view()
discovers this metadata automatically.

Run: uv run examples/views_joins_ctes.py
"""

import asyncio
from deebase import Database, ForeignKey, Text


async def main():
    print("=" * 60)
    print("DeeBase: Views for Joins and CTEs")
    print("=" * 60)

    # Create in-memory database
    db = Database("sqlite+aiosqlite:///:memory:")

    # =========================================================================
    # SETUP: Create tables with relationships
    # =========================================================================
    print("\n--- Setting Up Tables ---")

    class Author:
        id: int
        name: str
        email: str
        bio: Text

    class Category:
        id: int
        name: str
        slug: str

    class Book:
        id: int
        author_id: ForeignKey[int, "author"]
        category_id: ForeignKey[int, "category"]
        title: str
        price: float
        sales: int = 0

    # Create tables
    authors = await db.create(Author, pk='id')
    categories = await db.create(Category, pk='id')
    books = await db.create(Book, pk='id')

    # Insert sample data
    alice = await authors.insert({
        "name": "Alice Chen",
        "email": "alice@example.com",
        "bio": "Python expert and author of several technical books."
    })
    bob = await authors.insert({
        "name": "Bob Smith",
        "email": "bob@example.com",
        "bio": "Data scientist and educator."
    })

    tech = await categories.insert({"name": "Technology", "slug": "tech"})
    science = await categories.insert({"name": "Data Science", "slug": "data-science"})

    await books.insert({
        "author_id": alice["id"],
        "category_id": tech["id"],
        "title": "Python Fundamentals",
        "price": 39.99,
        "sales": 1500
    })
    await books.insert({
        "author_id": alice["id"],
        "category_id": tech["id"],
        "title": "Async Python Patterns",
        "price": 49.99,
        "sales": 800
    })
    await books.insert({
        "author_id": bob["id"],
        "category_id": science["id"],
        "title": "Data Science Handbook",
        "price": 59.99,
        "sales": 2500
    })
    await books.insert({
        "author_id": bob["id"],
        "category_id": tech["id"],
        "title": "Machine Learning Basics",
        "price": 44.99,
        "sales": 1200
    })

    print(f"Created {len(await authors())} authors")
    print(f"Created {len(await categories())} categories")
    print(f"Created {len(await books())} books")

    # =========================================================================
    # PATTERN 1: View for Repeated Joins
    # =========================================================================
    print("\n--- Pattern 1: View for Repeated Joins ---")
    print("Creating a view that joins books with authors and categories...")

    book_details = await db.create_view(
        "book_details",
        """
        SELECT
            b.id,
            b.title,
            b.price,
            b.sales,
            a.name as author_name,
            a.email as author_email,
            c.name as category_name,
            c.slug as category_slug
        FROM book b
        JOIN author a ON b.author_id = a.id
        JOIN category c ON b.category_id = c.id
        """
    )

    # Use like any table
    all_book_details = await book_details()
    print(f"\nAll books with details ({len(all_book_details)} rows):")
    for book in all_book_details:
        print(f"  '{book['title']}' by {book['author_name']} "
              f"[{book['category_name']}] - ${book['price']}")

    # With limit
    print("\nTop 2 books:")
    top_books = await book_details(limit=2)
    for book in top_books:
        print(f"  {book['title']}")

    # Lookup by column
    print("\nLooking up books by Alice Chen:")
    alice_book = await book_details.lookup(author_name="Alice Chen")
    print(f"  Found: {alice_book['title']}")

    # =========================================================================
    # PATTERN 2: Dataclass Support for Views
    # =========================================================================
    print("\n--- Pattern 2: Dataclass Support for Views ---")
    print("Generating dataclass from view for type-safe access...")

    BookDetailDC = book_details.dataclass()
    print(f"Generated dataclass: {BookDetailDC.__name__}")

    typed_books = await book_details()
    print("\nType-safe field access:")
    for book in typed_books:
        # IDE autocomplete works on these fields!
        revenue = book.price * book.sales
        print(f"  {book.title} by {book.author_name}: "
              f"{book.sales} sales, ${revenue:,.2f} revenue")

    # =========================================================================
    # PATTERN 3: Raw SQL for One-Off Joins
    # =========================================================================
    print("\n--- Pattern 3: Raw SQL for One-Off Joins ---")
    print("Complex aggregation query using db.q()...")

    author_stats = await db.q("""
        SELECT
            a.name,
            COUNT(b.id) as book_count,
            SUM(b.sales) as total_sales,
            ROUND(AVG(b.price), 2) as avg_price,
            SUM(b.price * b.sales) as total_revenue
        FROM author a
        LEFT JOIN book b ON a.id = b.author_id
        GROUP BY a.id, a.name
        ORDER BY total_revenue DESC
    """)

    print("\nAuthor statistics:")
    for stat in author_stats:
        print(f"  {stat['name']}:")
        print(f"    Books: {stat['book_count']}")
        print(f"    Total Sales: {stat['total_sales']}")
        print(f"    Avg Price: ${stat['avg_price']}")
        print(f"    Total Revenue: ${stat['total_revenue']:,.2f}")

    # =========================================================================
    # PATTERN 4: View for Dashboard Aggregations
    # =========================================================================
    print("\n--- Pattern 4: View for Dashboard Aggregations ---")
    print("Creating a category summary view...")

    await db.create_view(
        "category_summary",
        """
        SELECT
            c.id,
            c.name as category_name,
            c.slug,
            COUNT(b.id) as book_count,
            COALESCE(SUM(b.sales), 0) as total_sales,
            COALESCE(ROUND(AVG(b.price), 2), 0) as avg_price
        FROM category c
        LEFT JOIN book b ON c.id = b.category_id
        GROUP BY c.id, c.name, c.slug
        """
    )

    # Access via db.v
    category_summary = db.v.category_summary
    summaries = await category_summary()
    print("\nCategory Summary (via db.v.category_summary):")
    for summary in summaries:
        print(f"  {summary['category_name']}: "
              f"{summary['book_count']} books, "
              f"{summary['total_sales']} sales, "
              f"avg ${summary['avg_price']}")

    # =========================================================================
    # PATTERN 5: CTE via Raw SQL
    # =========================================================================
    print("\n--- Pattern 5: CTE (Common Table Expression) via Raw SQL ---")
    print("Finding authors with above-average sales using CTE...")

    cte_results = await db.q("""
        WITH author_totals AS (
            SELECT
                a.id,
                a.name,
                SUM(b.sales) as total_sales
            FROM author a
            JOIN book b ON a.id = b.author_id
            GROUP BY a.id, a.name
        ),
        avg_sales AS (
            SELECT AVG(total_sales) as avg_total
            FROM author_totals
        )
        SELECT
            at.name,
            at.total_sales,
            (at.total_sales - avg_sales.avg_total) as above_avg_by
        FROM author_totals at, avg_sales
        WHERE at.total_sales > avg_sales.avg_total
        ORDER BY at.total_sales DESC
    """)

    avg_sales = sum(r['total_sales'] for r in author_stats) / len(author_stats) if author_stats else 0
    print(f"\nAverage sales per author: {avg_sales:.0f}")
    print("Authors with above-average total sales:")
    for result in cte_results:
        print(f"  {result['name']}: {result['total_sales']} sales "
              f"(+{result['above_avg_by']:.0f} above avg)")

    if not cte_results:
        print("  (No authors above average - all are equal!)")

    # =========================================================================
    # PATTERN 6: Avoiding N+1 with Views
    # =========================================================================
    print("\n--- Pattern 6: Avoiding N+1 Queries ---")

    print("\nBAD: N+1 pattern (don't do this in production):")
    print("  # for book in books:")
    print("  #     author = await books.fk.author_id(book)  # N queries!")

    print("\nGOOD: View with JOIN (1 query):")
    print("  book_details = await db.create_view('book_details', 'SELECT ... JOIN ...')")
    print("  all_data = await book_details()  # 1 query!")

    all_with_join = await book_details()
    print(f"\n  Retrieved {len(all_with_join)} books with author info in 1 query")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 60)
    print("Summary: Views for Joins and CTEs")
    print("=" * 60)
    print("""
Use Cases:
  - db.create_view()  - Repeated join queries, dashboard data
  - db.v.viewname     - Access created/reflected views
  - view.dataclass()  - Type-safe access to join results
  - db.q()            - One-off joins, CTEs, complex aggregations

Benefits:
  - No N+1 query problem
  - Full DeeBase API on views (select, lookup, xtra, dataclass)
  - Database handles JOIN optimization
  - No Python class needed - schema discovered from database
  - SQL is the right tool for JOINs
""")

    await db.close()
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
