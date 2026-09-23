"""API layer for user management."""

from typing import Any

from src.models import User


class UserAPI:
    """Simple in-memory user API.

    BUG: create_user passes name=None when name is not provided,
    but User model requires name to be a string.
    """

    def __init__(self) -> None:
        self._users: dict[int, User] = {}
        self._next_id = 1

    def create_user(self, email: str, name: str | None = None, role: str = "viewer") -> dict[str, Any]:
        """Create a new user.

        BUG: When name is None, this passes None to User(), which causes
        a type error because User.name expects str, not None.
        """
        user = User(
            id=self._next_id,
            name=name,  # BUG: passes None when name not provided
            email=email,
            role=role,
        )
        self._users[user.id] = user
        self._next_id += 1
        return user.to_dict()

    def get_user(self, user_id: int) -> dict[str, Any] | None:
        user = self._users.get(user_id)
        return user.to_dict() if user else None

    def list_users(self) -> list[dict[str, Any]]:
        return [u.to_dict() for u in self._users.values()]

    def update_user(self, user_id: int, **kwargs: Any) -> dict[str, Any] | None:
        user = self._users.get(user_id)
        if user is None:
            return None
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        return user.to_dict()

    def deactivate_user(self, user_id: int) -> bool:
        user = self._users.get(user_id)
        if user is None:
            return False
        user.active = False
        return True
