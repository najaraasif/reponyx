from functools import wraps


def requires_auth(function):
    @wraps(function)
    def wrapper(user):
        return function(user)

    return wrapper


class AuthService:
    def reset_password(self, email: str) -> bool:
        return bool(email)
