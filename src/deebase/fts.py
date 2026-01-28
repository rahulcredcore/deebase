"""Full-Text Search (FTS) support for DeeBase.

Provides BM25 full-text search using:
- SQLite FTS5 virtual tables with sync triggers
- PostgreSQL pg_textsearch extension with BM25 indexes

Usage:
    from deebase import FTSIndex

    articles = await db.create(Article, pk='id', indexes=[
        FTSIndex("title", "content", language="english"),
    ])

    results = await articles.search("getting started", limit=10)
"""

from __future__ import annotations

from typing import Optional, Any


class FTSIndex:
    """Full-text search index definition.

    Unlike regular Index (B-tree), FTSIndex creates dialect-specific FTS structures:
    - SQLite: FTS5 virtual table + sync triggers
    - PostgreSQL: pg_textsearch BM25 index

    Args:
        *columns: Column names to include in the FTS index
        name: Optional index name. Auto-generated if not provided.
        language: Language for stemming/tokenization (default: "english")

    Example:
        from deebase import FTSIndex

        # Multi-column FTS index
        FTSIndex("title", "content", language="english")

        # Single-column with explicit name
        FTSIndex("title", name="title_fts")
    """

    def __init__(self, *columns: str, name: Optional[str] = None, language: str = "english"):
        if not columns:
            raise ValueError("FTSIndex requires at least one column")
        self.columns = list(columns)
        self.name = name
        self.language = language

    def __repr__(self) -> str:
        cols = ", ".join(f'"{c}"' for c in self.columns)
        parts = [cols]
        if self.name:
            parts.append(f'name="{self.name}"')
        if self.language != "english":
            parts.append(f'language="{self.language}"')
        return f"FTSIndex({', '.join(parts)})"


def _fts_table_name(table_name: str, index_name: Optional[str] = None) -> str:
    """Generate the FTS virtual table name for SQLite.

    Args:
        table_name: Source table name
        index_name: Optional explicit name

    Returns:
        FTS virtual table name (e.g., "article_fts" or the given name)
    """
    if index_name:
        return index_name
    return f"{table_name}_fts"


def generate_sqlite_fts_sql(
    table_name: str,
    columns: list[str],
    pk_column: str,
    index_name: Optional[str] = None,
    language: str = "english",
) -> list[str]:
    """Generate SQL statements to create SQLite FTS5 virtual table + triggers.

    Creates:
    1. FTS5 virtual table with content= pointing to source table
    2. INSERT trigger to sync new rows
    3. UPDATE trigger to sync changed rows
    4. DELETE trigger to sync removed rows
    5. Initial population from existing data

    Args:
        table_name: Source table name
        columns: Columns to index
        pk_column: Primary key column name (used as content_rowid)
        index_name: Optional FTS table name
        language: Tokenizer language

    Returns:
        List of SQL statements to execute in order
    """
    fts_name = _fts_table_name(table_name, index_name)
    cols_csv = ", ".join(columns)

    stmts = []

    # 1. Create FTS5 virtual table
    # content= links to source table, content_rowid= maps to PK
    fts_cols = ", ".join(columns)
    stmts.append(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS {fts_name} USING fts5("
        f"{fts_cols}, "
        f"content='{table_name}', "
        f"content_rowid='{pk_column}', "
        f"tokenize='porter unicode61'"
        f")"
    )

    # 2. INSERT trigger — add to FTS when row inserted into source
    new_cols = ", ".join(f"new.{c}" for c in columns)
    stmts.append(
        f"CREATE TRIGGER IF NOT EXISTS {fts_name}_ai AFTER INSERT ON {table_name} BEGIN "
        f"INSERT INTO {fts_name}(rowid, {cols_csv}) VALUES (new.{pk_column}, {new_cols}); "
        f"END"
    )

    # 3. DELETE trigger — remove from FTS when row deleted from source
    old_cols = ", ".join(f"old.{c}" for c in columns)
    stmts.append(
        f"CREATE TRIGGER IF NOT EXISTS {fts_name}_ad AFTER DELETE ON {table_name} BEGIN "
        f"INSERT INTO {fts_name}({fts_name}, rowid, {cols_csv}) VALUES ('delete', old.{pk_column}, {old_cols}); "
        f"END"
    )

    # 4. UPDATE trigger — remove old + add new
    stmts.append(
        f"CREATE TRIGGER IF NOT EXISTS {fts_name}_au AFTER UPDATE ON {table_name} BEGIN "
        f"INSERT INTO {fts_name}({fts_name}, rowid, {cols_csv}) VALUES ('delete', old.{pk_column}, {old_cols}); "
        f"INSERT INTO {fts_name}(rowid, {cols_csv}) VALUES (new.{pk_column}, {new_cols}); "
        f"END"
    )

    # 5. Populate FTS from existing data
    stmts.append(
        f"INSERT INTO {fts_name}(rowid, {cols_csv}) "
        f"SELECT {pk_column}, {cols_csv} FROM {table_name}"
    )

    return stmts


def generate_sqlite_fts_drop_sql(
    table_name: str,
    index_name: Optional[str] = None,
) -> list[str]:
    """Generate SQL to drop an FTS5 virtual table and its triggers.

    Args:
        table_name: Source table name
        index_name: FTS table name (auto-derived if not given)

    Returns:
        List of SQL statements
    """
    fts_name = _fts_table_name(table_name, index_name)
    return [
        f"DROP TRIGGER IF EXISTS {fts_name}_ai",
        f"DROP TRIGGER IF EXISTS {fts_name}_ad",
        f"DROP TRIGGER IF EXISTS {fts_name}_au",
        f"DROP TABLE IF EXISTS {fts_name}",
    ]


def _escape_fts5_query(query: str) -> str:
    """Escape a query string for safe use with FTS5 MATCH.

    Wraps each token in double quotes so special characters
    (hyphens, apostrophes, etc.) are treated as literals.

    Args:
        query: Raw search query

    Returns:
        Escaped FTS5 query string
    """
    # Replace double quotes inside the query to avoid breaking quoting
    tokens = query.split()
    escaped = []
    for token in tokens:
        # Remove any existing double quotes and wrap in quotes
        clean = token.replace('"', '')
        if clean:
            escaped.append(f'"{clean}"')
    return " ".join(escaped)


def generate_sqlite_search_sql(
    table_name: str,
    fts_name: str,
    pk_column: str,
    query: str,
    columns: Optional[list[str]] = None,
    limit: Optional[int] = None,
    score: bool = False,
) -> tuple[str, list[Any]]:
    """Generate SQL for an FTS5 search query.

    Args:
        table_name: Source table name
        fts_name: FTS virtual table name
        pk_column: Primary key column
        query: Search query string
        columns: Optional column filter (FTS5 column filter syntax)
        limit: Max results
        score: If True, include BM25 score

    Returns:
        Tuple of (sql_string, params)
    """
    safe_query = _escape_fts5_query(query)

    # Build the match expression
    if columns:
        # FTS5 column filter: {col1 col2}: query
        col_filter = " ".join(columns)
        match_expr = f"{{{col_filter}}} : {safe_query}"
    else:
        match_expr = safe_query

    if score:
        sql = (
            f"SELECT {table_name}.*, bm25({fts_name}) AS _score "
            f"FROM {fts_name} "
            f"JOIN {table_name} ON {table_name}.{pk_column} = {fts_name}.rowid "
            f"WHERE {fts_name} MATCH :query "
            f"ORDER BY bm25({fts_name})"
        )
    else:
        sql = (
            f"SELECT {table_name}.* "
            f"FROM {fts_name} "
            f"JOIN {table_name} ON {table_name}.{pk_column} = {fts_name}.rowid "
            f"WHERE {fts_name} MATCH :query "
            f"ORDER BY bm25({fts_name})"
        )

    if limit is not None:
        sql += f" LIMIT {int(limit)}"

    return sql, {"query": match_expr}


def generate_pg_fts_create_sql(
    table_name: str,
    columns: list[str],
    index_name: Optional[str] = None,
    language: str = "english",
) -> list[str]:
    """Generate SQL to create pg_textsearch BM25 indexes on PostgreSQL.

    Uses the pg_textsearch extension (TigerData/Timescale) which provides
    the ``USING bm25`` index access method and the ``<@>`` scoring operator.

    One BM25 index is created per column (pg_textsearch indexes a single
    column each). For multi-column FTS, multiple indexes are created and
    scores are combined at query time.

    Requires: ``CREATE EXTENSION pg_textsearch``

    Args:
        table_name: Source table name
        columns: Columns to index
        index_name: Optional base index name (suffixed with column name for
            multi-column indexes). Defaults to ``{table}_fts``.
        language: PostgreSQL text search configuration (default: "english")

    Returns:
        List of SQL statements
    """
    base_name = index_name or f"{table_name}_fts"

    stmts = []

    # Ensure extension exists
    stmts.append("CREATE EXTENSION IF NOT EXISTS pg_textsearch")

    # pg_textsearch: one index per column
    if len(columns) == 1:
        stmts.append(
            f"CREATE INDEX IF NOT EXISTS {base_name} ON {table_name} "
            f"USING bm25 ({columns[0]}) "
            f"WITH (text_config='{language}')"
        )
    else:
        for col in columns:
            idx_name = f"{base_name}_{col}"
            stmts.append(
                f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table_name} "
                f"USING bm25 ({col}) "
                f"WITH (text_config='{language}')"
            )

    return stmts


def generate_pg_fts_drop_sql(
    table_name: str,
    columns: list[str],
    index_name: Optional[str] = None,
) -> list[str]:
    """Generate SQL to drop PostgreSQL BM25 indexes.

    Mirrors ``generate_pg_fts_create_sql`` naming convention.

    Args:
        table_name: Source table name
        columns: Columns that were indexed
        index_name: Base index name used at creation time

    Returns:
        List of SQL statements
    """
    base_name = index_name or f"{table_name}_fts"

    if len(columns) == 1:
        return [f"DROP INDEX IF EXISTS {base_name}"]
    else:
        return [f"DROP INDEX IF EXISTS {base_name}_{col}" for col in columns]


def generate_pg_search_sql(
    table_name: str,
    columns: list[str],
    query: str,
    index_name: Optional[str] = None,
    language: str = "english",
    limit: Optional[int] = None,
    score: bool = False,
    search_columns: Optional[list[str]] = None,
) -> tuple[str, dict[str, Any]]:
    """Generate SQL for a PostgreSQL pg_textsearch search query.

    Uses the ``<@>`` operator which returns negative BM25 scores natively
    (more negative = more relevant), matching SQLite FTS5 ``bm25()`` semantics.

    For multi-column indexes, scores from each column are summed.

    Args:
        table_name: Source table name
        columns: All columns in the FTS index
        query: Search query string
        index_name: Base index name (for ``to_bm25query()``)
        language: Text search configuration
        limit: Max results
        score: If True, include BM25 score as ``_score``
        search_columns: Subset of columns to search (defaults to all)

    Returns:
        Tuple of (sql_string, params)
    """
    base_name = index_name or f"{table_name}_fts"
    cols = search_columns or columns

    # Build score expression: sum of <@> scores across searched columns
    # Each <@> returns a negative BM25 score
    if len(cols) == 1:
        col = cols[0]
        idx = base_name if len(columns) == 1 else f"{base_name}_{col}"
        score_expr = f"{col} <@> to_bm25query(:query, '{idx}')"
    else:
        parts = []
        for col in cols:
            idx = f"{base_name}_{col}"
            parts.append(f"{col} <@> to_bm25query(:query, '{idx}')")
        score_expr = " + ".join(parts)

    # Use the first column's operator for the WHERE filter
    first_col = cols[0]
    first_idx = base_name if len(columns) == 1 else f"{base_name}_{first_col}"
    where_expr = f"{first_col} <@> to_bm25query(:query, '{first_idx}') < 0"

    if score:
        sql = (
            f"SELECT {table_name}.*, ({score_expr}) AS _score "
            f"FROM {table_name} "
            f"WHERE {where_expr} "
            f"ORDER BY _score"
        )
    else:
        sql = (
            f"SELECT {table_name}.* "
            f"FROM {table_name} "
            f"WHERE {where_expr} "
            f"ORDER BY {score_expr}"
        )

    if limit is not None:
        sql += f" LIMIT {int(limit)}"

    return sql, {"query": query}
