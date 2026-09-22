from app.auth import AuthService


def fixture_test_reset() -> bool:
    return AuthService().reset_password("person@example.com")
