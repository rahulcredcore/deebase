"""Code generation command for DeeBase CLI.

Commands:
    deebase codegen              - Generate models from all tables
    deebase codegen users posts  - Generate models from specific tables
"""

import click
import sys
from pathlib import Path

from .utils import run_async
from .state import find_project_root, load_config, load_env


@click.command()
@click.argument('tables', nargs=-1)
@click.option('--output', '-o', help='Output file path (overrides config)')
def codegen(tables: tuple, output: str):
    """Generate Python model code from database tables.

    Without arguments, generates models for all tables.
    Specify table names to generate models for specific tables only.

    Examples:

        # Generate all models
        deebase codegen

        # Generate specific tables
        deebase codegen users posts comments

        # Custom output path
        deebase codegen --output src/myapp/db/models.py
    """
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        sys.exit(1)

    # Load configuration
    load_env(project_root)
    config = load_config(project_root)

    # Determine output path
    output_path = Path(output) if output else project_root / config.models_output

    click.echo(f"Generating models to: {output_path}")

    try:
        table_list = list(tables) if tables else None
        code = run_async(_generate_models(config, table_list))

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the code
        output_path.write_text(code)
        click.echo(f"Models generated successfully!")

    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


async def _generate_models(config, table_names: list[str] | None) -> str:
    """Generate model code from database tables."""
    from deebase import Database
    from deebase.dataclass_utils import dataclass_src
    import sqlalchemy as sa

    url = config.get_database_url()
    db = Database(url)

    try:
        # Get table names if not specified
        if table_names is None:
            async with db.engine.connect() as conn:
                def _get_tables(sync_conn):
                    inspector = sa.inspect(sync_conn)
                    return inspector.get_table_names()

                table_names = await conn.run_sync(_get_tables)

        if not table_names:
            return '"""Auto-generated database models."""\n\n# No tables found in database.\n'

        # Reflect all tables
        await db.reflect()

        # Generate dataclass source for each table
        sources = []
        all_imports = set()
        all_imports.add("from dataclasses import dataclass")
        all_imports.add("from typing import Optional")

        for table_name in sorted(table_names):
            try:
                table = db.t[table_name]
                dc = table.dataclass()

                # Generate source
                src = dataclass_src(dc)

                # Extract imports
                for line in src.split('\n'):
                    if line.startswith('from ') or line.startswith('import '):
                        all_imports.add(line)

                # Extract just the class definition
                class_lines = []
                in_class = False
                for line in src.split('\n'):
                    if line.startswith('@dataclass') or line.startswith('class '):
                        in_class = True
                    if in_class:
                        class_lines.append(line)

                sources.append('\n'.join(class_lines))

            except Exception as e:
                sources.append(f"# Error generating {table_name}: {e}")

        # Build final output
        output_lines = [
            '"""Auto-generated database models from DeeBase."""',
            '',
        ]
        output_lines.extend(sorted(all_imports))
        output_lines.append('')
        output_lines.append('')

        for i, class_src in enumerate(sources):
            if i > 0:
                output_lines.append('')
                output_lines.append('')
            output_lines.append(class_src)

        output_lines.append('')

        return '\n'.join(output_lines)

    finally:
        await db.close()
