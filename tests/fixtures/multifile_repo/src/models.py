"""User model for the demo API."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class User:
    """A user in the system.

    BUG: name field is required but API expects it to be optional with default "".
    The API passes name=None when creating users without a name, but the model
    requires a non-None string value.
    """

    id: int
    name: str  # BUG: should allow None or have default ""
    email: str
    role: str = "viewer"
    active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "User":
        return cls(
            id=data["id"],
            name=data.get("name", ""),  # BUG: this works, but to_dict doesn't handle None
            email=data["email"],
            role=data.get("role", "viewer"),
            active=data.get("active", True),
        )
