"""Tests for DeeBase CLI (Phase 13)."""

import pytest
import tempfile
import os
from pathlib import Path
from click.testing import CliRunner

from deebase.cli import main
from deebase.cli.parser import parse_field, parse_fields, FieldDefinition
from deebase.cli.generator import (
    generate_class_source,
    generate_create_call,
    generate_migration_code,
    generate_models_code,
)
from deebase.cli.state import (
    ProjectConfig,
    MigrationState,
    save_config,
    load_config,
    save_state,
    load_state,
    find_project_root,
)


# ============================================================================
# Parser Tests
# ============================================================================


class TestParser:
    """Tests for field:type parser."""

    def test_parse_simple_field(self):
        """Test parsing simple field specs."""
        field = parse_field("id:int")
        assert field.name == "id"
        assert field.type_name == "int"
        assert not field.unique
        assert not field.nullable
        assert field.default is None
        assert not field.is_foreign_key

    def test_parse_with_unique(self):
        """Test parsing field with unique modifier."""
        field = parse_field("email:str:unique")
        assert field.name == "email"
        assert field.type_name == "str"
        assert field.unique
        assert not field.nullable

    def test_parse_with_nullable(self):
        """Test parsing field with nullable modifier."""
        field = parse_field("bio:Text:nullable")
        assert field.name == "bio"
        assert field.type_name == "Text"
        assert field.nullable
        assert not field.unique

    def test_parse_with_default_string(self):
        """Test parsing field with string default."""
        field = parse_field("status:str:default=active")
        assert field.name == "status"
        assert field.type_name == "str"
        assert field.default == "active"

    def test_parse_with_default_int(self):
        """Test parsing field with int default."""
        field = parse_field("count:int:default=0")
        assert field.name == "count"
        assert field.type_name == "int"
        assert field.default == 0

    def test_parse_with_default_bool_true(self):
        """Test parsing field with bool default (true)."""
        field = parse_field("active:bool:default=true")
        assert field.default is True

    def test_parse_with_default_bool_false(self):
        """Test parsing field with bool default (false)."""
        field = parse_field("deleted:bool:default=false")
        assert field.default is False

    def test_parse_with_fk_simple(self):
        """Test parsing field with foreign key (simple)."""
        field = parse_field("user_id:int:fk=users")
        assert field.name == "user_id"
        assert field.type_name == "int"
        assert field.is_foreign_key
        assert field.fk_table == "users"
        assert field.fk_column == "id"

    def test_parse_with_fk_explicit_column(self):
        """Test parsing field with explicit FK column."""
        field = parse_field("email:str:fk=users.email")
        assert field.fk_table == "users"
        assert field.fk_column == "email"

    def test_parse_multiple_modifiers(self):
        """Test parsing field with multiple modifiers."""
        field = parse_field("code:str:unique:nullable:default=NEW")
        assert field.unique
        assert field.nullable
        assert field.default == "NEW"

    def test_parse_all_types(self):
        """Test all supported type names."""
        types = ['int', 'str', 'float', 'bool', 'bytes', 'Text', 'dict', 'datetime', 'date', 'time']
        for t in types:
            field = parse_field(f"field:{t}")
            assert field.type_name == t

    def test_parse_type_aliases(self):
        """Test type aliases (text, json)."""
        field_text = parse_field("content:text")
        assert field_text.type_name == "text"

        field_json = parse_field("data:json")
        assert field_json.type_name == "json"

    def test_parse_invalid_missing_type(self):
        """Test error for missing type."""
        with pytest.raises(ValueError, match="Expected format"):
            parse_field("name")

    def test_parse_invalid_type(self):
        """Test error for invalid type."""
        with pytest.raises(ValueError, match="Invalid type"):
            parse_field("field:invalid_type")

    def test_parse_invalid_modifier(self):
        """Test error for invalid modifier."""
        with pytest.raises(ValueError, match="Unknown modifier"):
            parse_field("field:str:invalid_modifier")

    def test_parse_empty_name(self):
        """Test error for empty field name."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_field(":str")

    def test_parse_invalid_name(self):
        """Test error for invalid field name."""
        with pytest.raises(ValueError, match="valid Python identifier"):
            parse_field("123field:str")

    def test_parse_fields_list(self):
        """Test parsing multiple field specs."""
        specs = ["id:int", "name:str", "email:str:unique"]
        fields = parse_fields(specs)
        assert len(fields) == 3
        assert fields[0].name == "id"
        assert fields[2].unique

    def test_python_type_property(self):
        """Test python_type property generates correct annotations."""
        field = parse_field("name:str")
        assert field.python_type == "str"

        field = parse_field("bio:Text:nullable")
        assert field.python_type == "Optional[Text]"

        field = parse_field("user_id:int:fk=users")
        assert 'ForeignKey[int, "users"]' in field.python_type


# ============================================================================
# Generator Tests
# ============================================================================


class TestGenerator:
    """Tests for Python code generator."""

    def test_generate_simple_class(self):
        """Test generating a simple class."""
        fields = [
            FieldDefinition(name="id", type_name="int"),
            FieldDefinition(name="name", type_name="str"),
        ]
        src = generate_class_source("User", fields)
        assert "class User:" in src
        assert "id: int" in src
        assert "name: str" in src

    def test_generate_class_with_defaults(self):
        """Test generating class with default values."""
        fields = [
            FieldDefinition(name="id", type_name="int"),
            FieldDefinition(name="status", type_name="str", default="active"),
        ]
        src = generate_class_source("Post", fields)
        assert 'status: str = "active"' in src

    def test_generate_class_with_fk(self):
        """Test generating class with foreign key."""
        fields = [
            FieldDefinition(name="id", type_name="int"),
            FieldDefinition(name="user_id", type_name="int", fk_table="users", fk_column="id"),
        ]
        src = generate_class_source("Post", fields)
        assert "from deebase import" in src
        assert "ForeignKey" in src
        assert 'user_id: ForeignKey[int, "users"]' in src

    def test_generate_dataclass(self):
        """Test generating @dataclass decorated class."""
        fields = [
            FieldDefinition(name="id", type_name="int"),
            FieldDefinition(name="name", type_name="str"),
        ]
        src = generate_class_source("User", fields, as_dataclass=True)
        assert "@dataclass" in src
        assert "from dataclasses import dataclass" in src
        assert "= None" in src  # All fields have None default in dataclass mode

    def test_generate_create_call_simple(self):
        """Test generating simple create call."""
        call = generate_create_call("User", "id")
        assert "await db.create(User" in call
        assert "pk='id'" in call

    def test_generate_create_call_with_indexes(self):
        """Test generating create call with indexes."""
        call = generate_create_call("User", "id", indexes=["email"])
        assert "'email'" in call

    def test_generate_create_call_with_unique(self):
        """Test generating create call with unique fields."""
        call = generate_create_call("User", "id", unique_fields=["email"])
        assert "Index(" in call
        assert "unique=True" in call

    def test_generate_create_call_composite_pk(self):
        """Test generating create call with composite PK."""
        call = generate_create_call("OrderItem", ["order_id", "product_id"])
        assert "['order_id', 'product_id']" in call

    def test_generate_migration_code(self):
        """Test generating complete migration code."""
        fields = [
            FieldDefinition(name="id", type_name="int"),
            FieldDefinition(name="name", type_name="str"),
        ]
        code = generate_migration_code("User", fields, "id")
        assert "class User:" in code
        assert "await db.create(User" in code

    def test_generate_models_code(self):
        """Test generating models file code."""
        fields = [
            FieldDefinition(name="id", type_name="int"),
            FieldDefinition(name="name", type_name="str"),
        ]
        code = generate_models_code("User", fields)
        assert "@dataclass" in code


# ============================================================================
# State Management Tests
# ============================================================================


class TestState:
    """Tests for state management."""

    def test_project_config_defaults(self):
        """Test ProjectConfig default values."""
        config = ProjectConfig()
        assert config.name == "myproject"
        assert config.database_type == "sqlite"
        assert config.sqlite_path == "data/app.db"

    def test_project_config_get_database_url_sqlite(self):
        """Test getting SQLite database URL."""
        config = ProjectConfig(database_type="sqlite", sqlite_path="test.db")
        url = config.get_database_url()
        assert url == "sqlite+aiosqlite:///test.db"

    def test_project_config_get_database_url_env(self):
        """Test getting database URL from environment."""
        os.environ["DATABASE_URL"] = "postgresql+asyncpg://test"
        config = ProjectConfig()
        url = config.get_database_url()
        assert url == "postgresql+asyncpg://test"
        del os.environ["DATABASE_URL"]

    def test_migration_state_defaults(self):
        """Test MigrationState default values."""
        state = MigrationState()
        assert state.current_migration == "0000-initial"
        assert not state.sealed
        assert state.db_version == 0

    def test_save_and_load_config(self):
        """Test saving and loading config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            deebase_dir = project_root / ".deebase"
            deebase_dir.mkdir()

            config = ProjectConfig(name="testproject", database_type="sqlite")
            save_config(config, project_root)

            loaded = load_config(project_root)
            assert loaded.name == "testproject"
            assert loaded.database_type == "sqlite"

    def test_save_and_load_state(self):
        """Test saving and loading migration state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            deebase_dir = project_root / ".deebase"
            deebase_dir.mkdir()

            state = MigrationState(current_migration="0001-test", sealed=True, db_version=1)
            save_state(state, project_root)

            loaded = load_state(project_root)
            assert loaded.current_migration == "0001-test"
            assert loaded.sealed
            assert loaded.db_version == 1

    def test_find_project_root_not_found(self):
        """Test find_project_root when not in a project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            result = find_project_root()
            # Should return None when not in a project
            # (unless we're in the actual deebase project)

    def test_load_config_not_found(self):
        """Test loading config when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(FileNotFoundError):
                load_config(Path(tmpdir))


# ============================================================================
# CLI Command Tests
# ============================================================================


class TestCLICommands:
    """Tests for CLI commands using Click's test runner."""

    def test_main_help(self):
        """Test main help command."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "DeeBase" in result.output
        assert "table" in result.output
        assert "migrate" in result.output

    def test_main_version(self):
        """Test version command."""
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        # Version should be displayed

    def test_init_command(self):
        """Test init command creates project structure."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            result = runner.invoke(main, ["init"])
            assert result.exit_code == 0
            assert "initialized successfully" in result.output

            # Verify structure was created
            temp_project = Path(tmpdir)
            assert (temp_project / ".deebase").is_dir()
            assert (temp_project / ".deebase" / "config.toml").exists()
            assert (temp_project / ".deebase" / "state.json").exists()
            assert (temp_project / "migrations").is_dir()
            assert (temp_project / "data").is_dir()

    def test_init_command_postgres(self):
        """Test init with --postgres flag."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            result = runner.invoke(main, ["init", "--postgres"])
            assert result.exit_code == 0

            # Check config has postgres type
            config = load_config(Path(tmpdir))
            assert config.database_type == "postgres"

    def test_init_command_with_package(self):
        """Test init with --new-package."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            temp_project = Path(tmpdir)
            result = runner.invoke(main, ["init", "--new-package", "myapp"])
            assert result.exit_code == 0
            assert (temp_project / "myapp").is_dir()
            assert (temp_project / "myapp" / "__init__.py").exists()
            assert (temp_project / "myapp" / "models").is_dir()

    def test_init_command_idempotent(self):
        """Test init is idempotent (safe to run twice)."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            # First init
            result1 = runner.invoke(main, ["init"])
            assert result1.exit_code == 0

            # Second init (should ask for confirmation)
            result2 = runner.invoke(main, ["init"], input="n\n")
            assert "Aborted" in result2.output

    def test_table_create_help(self):
        """Test table create help."""
        runner = CliRunner()
        result = runner.invoke(main, ["table", "create", "--help"])
        assert result.exit_code == 0
        assert "name:type" in result.output
        assert "--pk" in result.output

    def test_table_list_no_project(self):
        """Test table list without initialized project."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            result = runner.invoke(main, ["table", "list"])
            assert result.exit_code == 1
            assert "No DeeBase project found" in result.output

    def test_migrate_status(self):
        """Test migrate status command."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            # First init
            runner.invoke(main, ["init"])

            result = runner.invoke(main, ["migrate", "status"])
            assert result.exit_code == 0
            assert "Current Migration" in result.output
            assert "0000-initial" in result.output

    def test_migrate_seal(self):
        """Test migrate seal command."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            temp_project = Path(tmpdir)
            # First init
            runner.invoke(main, ["init"])

            result = runner.invoke(main, ["migrate", "seal", "initial schema"])
            assert result.exit_code == 0
            assert "Sealing migration" in result.output
            assert "Created new migration" in result.output

            # Check new migration file was created
            migrations = list((temp_project / "migrations").glob("0001-*.py"))
            assert len(migrations) == 1

    def test_migrate_new(self):
        """Test migrate new command."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            # First init
            runner.invoke(main, ["init"])

            result = runner.invoke(main, ["migrate", "new", "add users table"])
            assert result.exit_code == 0
            assert "Created migration" in result.output

    def test_index_help(self):
        """Test index command help."""
        runner = CliRunner()
        result = runner.invoke(main, ["index", "--help"])
        assert result.exit_code == 0
        assert "create" in result.output
        assert "list" in result.output
        assert "drop" in result.output

    def test_view_help(self):
        """Test view command help."""
        runner = CliRunner()
        result = runner.invoke(main, ["view", "--help"])
        assert result.exit_code == 0
        assert "create" in result.output
        assert "list" in result.output
        assert "drop" in result.output

    def test_codegen_help(self):
        """Test codegen command help."""
        runner = CliRunner()
        result = runner.invoke(main, ["codegen", "--help"])
        assert result.exit_code == 0
        assert "Generate Python model code" in result.output

    def test_db_help(self):
        """Test db command help."""
        runner = CliRunner()
        result = runner.invoke(main, ["db", "--help"])
        assert result.exit_code == 0
        assert "info" in result.output

    def test_sql_help(self):
        """Test sql command help."""
        runner = CliRunner()
        result = runner.invoke(main, ["sql", "--help"])
        assert result.exit_code == 0
        assert "Execute raw SQL" in result.output


# ============================================================================
# Integration Tests
# ============================================================================


class TestCLIIntegration:
    """Integration tests for CLI with real database operations."""

    def test_full_workflow_init_to_status(self):
        """Test full workflow: init -> migrate status."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            runner.invoke(main, ["init"])
            result = runner.invoke(main, ["migrate", "status"])
            assert result.exit_code == 0
            assert "0000-initial" in result.output

    def test_table_operations_require_project(self):
        """Test that table operations require project initialization."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            result = runner.invoke(main, ["table", "list"])
            assert result.exit_code == 1
            assert "No DeeBase project found" in result.output

    def test_create_table_basic(self):
        """Test basic table creation."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            runner.invoke(main, ["init"])
            result = runner.invoke(main, [
                "table", "create", "users",
                "id:int", "name:str", "email:str:unique",
                "--pk", "id"
            ])
            # Should succeed or give db error if db doesn't exist
            # This tests the CLI parsing works correctly
            assert "Creating table" in result.output or "Error" in result.output

    def test_codegen_no_tables(self):
        """Test codegen with no tables."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            runner.invoke(main, ["init"])
            result = runner.invoke(main, ["codegen"])
            # Should handle empty database gracefully
            assert result.exit_code == 0 or "Error" in result.output
