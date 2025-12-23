"""Tests for dataclass utilities."""

import pytest
from dataclasses import dataclass, fields
from typing import Optional
import sqlalchemy as sa

from deebase.dataclass_utils import (
    extract_annotations,
    make_table_dataclass,
    sqlalchemy_type_to_python,
    record_to_dict,
    dict_to_dataclass,
)


class TestExtractAnnotations:
    """Tests for extract_annotations function."""

    def test_simple_class(self):
        """Test extracting annotations from a simple class."""
        class User:
            id: int
            name: str
            age: int

        annotations = extract_annotations(User)
        assert annotations == {"id": int, "name": str, "age": int}

    def test_class_with_optional(self):
        """Test extracting annotations with Optional types."""
        class User:
            id: int
            name: str
            email: Optional[str]

        annotations = extract_annotations(User)
        assert "id" in annotations
        assert "name" in annotations
        assert "email" in annotations

    def test_empty_class(self):
        """Test class with no annotations."""
        class Empty:
            pass

        annotations = extract_annotations(Empty)
        assert annotations == {}


class TestSQLAlchemyTypeToPython:
    """Tests for sqlalchemy_type_to_python function."""

    def test_integer_mapping(self):
        """Test Integer maps to int."""
        result = sqlalchemy_type_to_python(sa.Integer())
        assert result == int

    def test_string_mapping(self):
        """Test String maps to str."""
        result = sqlalchemy_type_to_python(sa.String())
        assert result == str

    def test_text_mapping(self):
        """Test Text maps to str."""
        result = sqlalchemy_type_to_python(sa.Text())
        assert result == str

    def test_float_mapping(self):
        """Test Float maps to float."""
        result = sqlalchemy_type_to_python(sa.Float())
        assert result == float

    def test_boolean_mapping(self):
        """Test Boolean maps to bool."""
        result = sqlalchemy_type_to_python(sa.Boolean())
        assert result == bool

    def test_datetime_mapping(self):
        """Test DateTime maps to datetime."""
        from datetime import datetime
        result = sqlalchemy_type_to_python(sa.DateTime())
        assert result == datetime

    def test_json_mapping(self):
        """Test JSON maps to dict."""
        result = sqlalchemy_type_to_python(sa.JSON())
        assert result == dict


class TestMakeTableDataclass:
    """Tests for make_table_dataclass function."""

    def test_simple_table(self):
        """Test generating dataclass from simple table."""
        metadata = sa.MetaData()
        table = sa.Table(
            "users",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String),
            sa.Column("age", sa.Integer),
        )

        User = make_table_dataclass("User", table)

        # Check it's a dataclass
        assert User.__name__ == "User"
        field_names = {f.name for f in fields(User)}
        assert field_names == {"id", "name", "age"}

    def test_all_fields_optional(self):
        """Test that all fields in generated dataclass are Optional."""
        metadata = sa.MetaData()
        table = sa.Table(
            "items",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("value", sa.String),
        )

        Item = make_table_dataclass("Item", table)

        # All fields should have default None
        field_list = fields(Item)
        for field in field_list:
            assert field.default is None


class TestRecordToDict:
    """Tests for record_to_dict function."""

    def test_dict_input(self):
        """Test that dict input is returned as-is."""
        data = {"id": 1, "name": "Alice"}
        result = record_to_dict(data)
        assert result == data

    def test_dataclass_input(self):
        """Test converting dataclass to dict."""
        @dataclass
        class User:
            id: int
            name: str

        user = User(id=1, name="Alice")
        result = record_to_dict(user)
        assert result == {"id": 1, "name": "Alice"}

    def test_object_input(self):
        """Test converting object with __dict__ to dict."""
        class User:
            def __init__(self):
                self.id = 1
                self.name = "Alice"

        user = User()
        result = record_to_dict(user)
        assert result == {"id": 1, "name": "Alice"}

    def test_object_filters_private_attributes(self):
        """Test that private attributes are filtered out."""
        class User:
            def __init__(self):
                self.id = 1
                self.name = "Alice"
                self._private = "secret"

        user = User()
        result = record_to_dict(user)
        assert result == {"id": 1, "name": "Alice"}
        assert "_private" not in result


class TestDictToDataclass:
    """Tests for dict_to_dataclass function."""

    def test_simple_conversion(self):
        """Test converting dict to dataclass."""
        @dataclass
        class User:
            id: int
            name: str

        data = {"id": 1, "name": "Alice"}
        user = dict_to_dataclass(data, User)

        assert isinstance(user, User)
        assert user.id == 1
        assert user.name == "Alice"

    def test_filters_extra_fields(self):
        """Test that extra fields in dict are ignored."""
        @dataclass
        class User:
            id: int
            name: str

        data = {"id": 1, "name": "Alice", "extra": "ignored"}
        user = dict_to_dataclass(data, User)

        assert user.id == 1
        assert user.name == "Alice"
        assert not hasattr(user, "extra")

    def test_non_dataclass_raises_error(self):
        """Test that non-dataclass raises ValueError."""
        class NotADataclass:
            id: int
            name: str

        with pytest.raises(ValueError, match="not a dataclass"):
            dict_to_dataclass({"id": 1}, NotADataclass)
