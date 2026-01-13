"""DeeBase Command-Line Interface.

A Click-based CLI for database management, table creation, code generation,
and migration preparation.

Commands:
    deebase init                - Initialize a new project
    deebase db info             - Show database info
    deebase db shell            - Interactive SQL shell
    deebase sql "..."           - Execute raw SQL
    deebase table create ...    - Create a table
    deebase table list          - List tables
    deebase table schema <name> - Show table schema
    deebase table drop <name>   - Drop a table
    deebase data insert ...     - Insert record(s)
    deebase data list <table>   - List records
    deebase data get <table> <pk> - Get a record
    deebase data update ...     - Update a record
    deebase data delete ...     - Delete a record
    deebase index create ...    - Create an index
    deebase index list <table>  - List indexes on a table
    deebase index drop <name>   - Drop an index
    deebase view create ...     - Create a view
    deebase view reflect <name> - Reflect an existing view
    deebase view list           - List views
    deebase view drop <name>    - Drop a view
    deebase codegen             - Generate model code from database
    deebase migrate seal        - Seal current migration
    deebase migrate status      - Show migration status
    deebase api init            - Initialize API structure
    deebase api serve           - Start development server
    deebase api generate        - Generate router code
"""

import click

from .init_cmd import init
from .db_cmd import db, sql
from .table_cmd import table
from .data_cmd import data
from .index_cmd import index
from .view_cmd import view
from .codegen_cmd import codegen
from .migrate_cmd import migrate
from .api_cmd import api
from .utils import run_async


@click.group()
@click.version_option(package_name="deebase")
def main():
    """DeeBase - Async SQLAlchemy-based database CLI.

    Manage databases, tables, indexes, views, and migrations.
    """
    pass


# Register command groups
main.add_command(init)
main.add_command(db)
main.add_command(sql)
main.add_command(table)
main.add_command(data)
main.add_command(index)
main.add_command(view)
main.add_command(codegen)
main.add_command(migrate)
main.add_command(api)


if __name__ == "__main__":
    main()
