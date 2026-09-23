"""Tests for the user API."""

import pytest

from src.api import UserAPI


class TestUserAPI:
    def setup_method(self) -> None:
        self.api = UserAPI()

    def test_create_user_with_name(self) -> None:
        result = self.api.create_user(email="alice@example.com", name="Alice")
        assert result["name"] == "Alice"
        assert result["email"] == "alice@example.com"
        assert result["role"] == "viewer"
        assert result["active"] is True

    def test_create_user_without_name(self) -> None:
        """BUG: This test fails because User model requires name to be str,
        but create_user passes None when name is not provided."""
        result = self.api.create_user(email="bob@example.com")
        # Expected: name should default to "" when not provided
        # Actual: TypeError because User.name expects str, not None
        assert result["name"] == ""

    def test_create_user_with_role(self) -> None:
        result = self.api.create_user(email="admin@example.com", name="Admin", role="admin")
        assert result["role"] == "admin"

    def test_get_user(self) -> None:
        self.api.create_user(email="test@example.com", name="Test")
        result = self.api.get_user(1)
        assert result is not None
        assert result["email"] == "test@example.com"

    def test_get_nonexistent_user(self) -> None:
        result = self.api.get_user(999)
        assert result is None

    def test_list_users(self) -> None:
        self.api.create_user(email="a@example.com", name="A")
        self.api.create_user(email="b@example.com", name="B")
        users = self.api.list_users()
        assert len(users) == 2

    def test_update_user(self) -> None:
        self.api.create_user(email="test@example.com", name="Test")
        result = self.api.update_user(1, name="Updated")
        assert result is not None
        assert result["name"] == "Updated"

    def test_deactivate_user(self) -> None:
        self.api.create_user(email="test@example.com", name="Test")
        assert self.api.deactivate_user(1) is True
        user = self.api.get_user(1)
        assert user is not None
        assert user["active"] is False

    def test_deactivate_nonexistent_user(self) -> None:
        assert self.api.deactivate_user(999) is False

    def test_to_dict_returns_all_fields(self) -> None:
        result = self.api.create_user(email="test@example.com", name="Test", role="admin")
        assert set(result.keys()) == {"id", "name", "email", "role", "active"}
