"""pyfamilysafety2 — Microsoft Family Safety Python library."""

from .api import FamilySafety
from .models import Child, DaySchedule, DayUsage, WeekSchedule, WeeklyUsage
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
    "DayUsage",
    "WeekSchedule",
    "WeeklyUsage",
    "FamilySafetyError",
    "AuthError",
    "AuthPendingError",
    "AuthExpiredError",
    "APIError",
]

__version__ = "1.0.0"
