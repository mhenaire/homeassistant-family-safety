"""pyfamilysafety2 — Microsoft Family Safety Python library."""

from .api import FamilySafety
from .models import Child, DaySchedule, WeekSchedule
from .exceptions import (
    FamilySafetyError,
    AuthError,
    AuthPendingError,
    AuthExpiredError,
    APIError,
)

__all__ = [
    "FamilySafety",
    "Child",
    "DaySchedule",
    "WeekSchedule",
    "FamilySafetyError",
    "AuthError",
    "AuthPendingError",
    "AuthExpiredError",
    "APIError",
]

__version__ = "1.0.0"
