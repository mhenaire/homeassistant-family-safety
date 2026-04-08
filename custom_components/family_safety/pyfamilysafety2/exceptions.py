"""Exceptions for pyfamilysafety2."""


class FamilySafetyError(Exception):
    """Base exception for all pyfamilysafety2 errors."""


class AuthError(FamilySafetyError):
    """Authentication failed."""


class AuthPendingError(AuthError):
    """Device code not yet approved by the user."""


class AuthExpiredError(AuthError):
    """Device code or refresh token has expired — re-authentication required."""


class APIError(FamilySafetyError):
    """API call failed."""

    def __init__(self, status: int, message: str) -> None:
        self.status = status
        super().__init__(f"API error {status}: {message}")
