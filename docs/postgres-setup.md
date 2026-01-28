# PostgreSQL Setup for DeeBase

DeeBase supports PostgreSQL via asyncpg. This guide covers setting up PostgreSQL for development and testing, including the pg_textsearch extension for BM25 full-text search.

## Standard PostgreSQL (without FTS)

If you only need core DeeBase features (CRUD, indexes, migrations, etc.) without BM25 full-text search:

```bash
docker run -d --name deebase-pg \
  -e POSTGRES_PASSWORD=deebase \
  -p 5432:5432 \
  postgres:17
```

Connection URL:
```
postgresql+asyncpg://postgres:deebase@localhost/postgres
```

## PostgreSQL with pg_textsearch (BM25 FTS)

The [pg_textsearch](https://github.com/timescale/pg_textsearch) extension (by TigerData/Timescale) adds BM25 ranked full-text search to PostgreSQL. There is no pre-built Docker image that includes it, so you need a custom Dockerfile.

### Dockerfile

```dockerfile
FROM postgres:17
RUN apt-get update && apt-get install -y git build-essential postgresql-server-dev-17 \
    && cd /tmp && git clone https://github.com/timescale/pg_textsearch \
    && cd pg_textsearch && make && make install \
    && rm -rf /tmp/pg_textsearch && apt-get purge -y git build-essential && apt-get autoremove -y
```

### Build and Run

```bash
# Build the image
docker build -t postgres-fts .

# Start the container
docker run -d --name deebase-pg \
  -e POSTGRES_PASSWORD=deebase \
  -p 5432:5432 \
  postgres-fts

# Enable the extension
docker exec -it deebase-pg psql -U postgres -c "CREATE EXTENSION pg_textsearch;"
```

### Verify

```bash
docker exec -it deebase-pg psql -U postgres -c "SELECT extname FROM pg_extension WHERE extname = 'pg_textsearch';"
```

Connection URL:
```
postgresql+asyncpg://postgres:deebase@localhost/postgres
```

## DeeBase Connection

```python
from deebase import Database

# SQLite (default, no setup needed)
db = Database("sqlite+aiosqlite:///myapp.db")

# PostgreSQL
db = Database("postgresql+asyncpg://postgres:deebase@localhost/postgres")
```

## References

- [pg_textsearch GitHub](https://github.com/timescale/pg_textsearch)
- [TigerData pg_textsearch docs](https://www.tigerdata.com/docs/use-timescale/latest/extensions/pg-textsearch)
- [asyncpg](https://github.com/MagicStack/asyncpg)
