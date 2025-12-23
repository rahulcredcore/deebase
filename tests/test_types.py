"""Tests for type mapping utilities."""

import pytest
from typing import Optional
from datetime import datetime, date, time
import sqlalchemy as sa

from deebase.types import python_type_to_sqlalchemy, is_optional, Text


class TestPythonTypeToSQLAlchemy:
    """Tests for python_type_to_sqlalchemy function."""

    def test_int_mapping(self):
        """Test int maps to Integer."""
        result = python_type_to_sqlalchemy(int)
        assert isinstance(result, sa.Integer)

    def test_str_mapping(self):
        """Test str maps to String."""
        result = python_type_to_sqlalchemy(str)
        assert isinstance(result, sa.String)

    def test_float_mapping(self):
        """Test float maps to Float."""
        result = python_type_to_sqlalchemy(float)
        assert isinstance(result, sa.Float)

    def test_bool_mapping(self):
        """Test bool maps to Boolean."""
        result = python_type_to_sqlalchemy(bool)
        assert isinstance(result, sa.Boolean)

    def test_bytes_mapping(self):
        """Test bytes maps to LargeBinary."""
        result = python_type_to_sqlalchemy(bytes)
        assert isinstance(result, sa.LargeBinary)

    def test_datetime_mapping(self):
        """Test datetime maps to DateTime."""
        result = python_type_to_sqlalchemy(datetime)
        assert isinstance(result, sa.DateTime)

    def test_date_mapping(self):
        """Test date maps to Date."""
        result = python_type_to_sqlalchemy(date)
        assert isinstance(result, sa.Date)

    def test_time_mapping(self):
        """Test time maps to Time."""
        result = python_type_to_sqlalchemy(time)
        assert isinstance(result, sa.Time)

    def test_text_mapping(self):
        """Test Text marker maps to Text (unlimited text)."""
        result = python_type_to_sqlalchemy(Text)
        assert isinstance(result, sa.Text)

    def test_dict_mapping(self):
        """Test dict maps to JSON."""
        result = python_type_to_sqlalchemy(dict)
        assert isinstance(result, sa.JSON)

    def test_optional_int_mapping(self):
        """Test Optional[int] maps to Integer."""
        result = python_type_to_sqlalchemy(Optional[int])
        assert isinstance(result, sa.Integer)

    def test_optional_str_mapping(self):
        """Test Optional[str] maps to String."""
        result = python_type_to_sqlalchemy(Optional[str])
        assert isinstance(result, sa.String)

    def test_optional_text_mapping(self):
        """Test Optional[Text] maps to Text."""
        result = python_type_to_sqlalchemy(Optional[Text])
        assert isinstance(result, sa.Text)

    def test_optional_dict_mapping(self):
        """Test Optional[dict] maps to JSON."""
        result = python_type_to_sqlalchemy(Optional[dict])
        assert isinstance(result, sa.JSON)

    def test_unsupported_type(self):
        """Test that unsupported types raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported type"):
            python_type_to_sqlalchemy(list)


class TestIsOptional:
    """Tests for is_optional function."""

    def test_optional_int(self):
        """Test Optional[int] is detected."""
        assert is_optional(Optional[int]) is True

    def test_optional_str(self):
        """Test Optional[str] is detected."""
        assert is_optional(Optional[str]) is True

    def test_non_optional_int(self):
        """Test int is not optional."""
        assert is_optional(int) is False

    def test_non_optional_str(self):
        """Test str is not optional."""
        assert is_optional(str) is False

    def test_non_optional_custom_type(self):
        """Test custom types are not optional."""
        class CustomType:
            pass
        assert is_optional(CustomType) is False
