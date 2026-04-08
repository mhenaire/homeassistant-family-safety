"""Data models for pyfamilysafety2."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import FamilySafetyClient

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# Allowance of 0 milliseconds means "no screen time allowed" (limit is 0 minutes).
# The API uses 0 to mean explicitly blocked, not unlimited.
# To represent "no limit set", isLimitSet=False in the API response.
_MS_PER_MINUTE = 60_000


@dataclass
class DaySchedule:
    """Screen time schedule for a single day."""

    day: str
    """Day name, lowercase (e.g. 'monday')."""

    allowance_minutes: int
    """Allowed screen time in minutes. 0 means no screen time allowed."""

    window_start: time
    """Start of the available window (device can be used from this time)."""

    window_end: time
    """End of the available window (device is blocked after this time)."""

    limit_enabled: bool
    """Whether a screen time limit is actively set for this day."""

    @property
    def allowance_hours(self) -> float:
        """Allowance in hours (float)."""
        return self.allowance_minutes / 60

    def __repr__(self) -> str:
        return (
            f"DaySchedule({self.day}: {self.allowance_minutes}min, "
            f"{self.window_start.strftime('%H:%M')}–{self.window_end.strftime('%H:%M')}, "
            f"enabled={self.limit_enabled})"
        )

    @classmethod
    def _from_api(cls, day: str, data: dict) -> "DaySchedule":
        allowance_ms = data.get("allowance", 0)
        intervals = data.get("allottedIntervals", [])
        if intervals:
            start = time.fromisoformat(intervals[0]["begin"])
            end = time.fromisoformat(intervals[0]["end"])
        else:
            start = time(0, 0)
            end = time(23, 59)
        return cls(
            day=day,
            allowance_minutes=allowance_ms // _MS_PER_MINUTE,
            window_start=start,
            window_end=end,
            limit_enabled=allowance_ms > 0,
        )

    def _to_patch_payload(self) -> dict:
        return {
            "allowance": self.allowance_minutes * _MS_PER_MINUTE,
            "allottedIntervals": [
                {
                    "begin": self.window_start.strftime("%H:%M:%S"),
                    "end": self.window_end.strftime("%H:%M:%S"),
                }
            ],
        }


@dataclass
class WeekSchedule:
    """Full week screen time schedule for a child on Windows."""

    days: dict[str, DaySchedule] = field(default_factory=dict)

    def __getitem__(self, day: str) -> DaySchedule:
        return self.days[day.lower()]

    def __iter__(self):
        return iter(self.days.values())

    def items(self):
        return self.days.items()

    def __repr__(self) -> str:
        lines = [f"WeekSchedule("]
        for d in DAYS:
            s = self.days.get(d)
            if s:
                lines.append(f"  {s}")
        lines.append(")")
        return "\n".join(lines)

    @classmethod
    def _from_api(cls, daily_restrictions: dict) -> "WeekSchedule":
        days = {}
        for day, data in daily_restrictions.items():
            days[day.lower()] = DaySchedule._from_api(day.lower(), data)
        return cls(days=days)


@dataclass
class Child:
    """A child (non-admin family member) with screen time management."""

    user_id: str
    """Microsoft account PUID for this child."""

    first_name: str
    """Child's first name."""

    display_name: str
    """Child's full display name."""

    _client: "FamilySafetyClient" = field(repr=False)

    def __repr__(self) -> str:
        return f"Child(name={self.first_name!r}, user_id={self.user_id!r})"

    async def get_schedule(self) -> WeekSchedule:
        """Fetch the current Windows screen time schedule for this child."""
        return await self._client.get_schedule(self.user_id)

    async def set_allowance(
        self,
        day: str,
        *,
        minutes: int,
        window_start: time | None = None,
        window_end: time | None = None,
    ) -> None:
        """Set the screen time allowance for a specific day.

        Args:
            day: Day name, e.g. 'monday', 'tuesday', etc.
            minutes: Allowed screen time in minutes. Use 0 to block entirely.
            window_start: Start of available window (keeps existing if not provided).
            window_end: End of available window (keeps existing if not provided).
        """
        day = day.lower()
        if day not in DAYS:
            raise ValueError(f"Invalid day {day!r}. Must be one of: {DAYS}")

        # Fetch current schedule to get existing window times if not overriding
        if window_start is None or window_end is None:
            schedule = await self.get_schedule()
            existing = schedule[day]
            window_start = window_start or existing.window_start
            window_end = window_end or existing.window_end

        await self._client.patch_schedule(
            self.user_id,
            day=day,
            allowance_minutes=minutes,
            window_start=window_start,
            window_end=window_end,
        )

    async def set_allowance_today(
        self,
        *,
        minutes: int,
        window_start: time | None = None,
        window_end: time | None = None,
    ) -> None:
        """Set the screen time allowance for today."""
        from datetime import datetime
        today = datetime.now().strftime("%A").lower()
        await self.set_allowance(
            today, minutes=minutes, window_start=window_start, window_end=window_end
        )

    async def add_allowance(self, day: str, *, minutes: int) -> None:
        """Add extra minutes to a specific day's screen time allowance.

        Args:
            day: Day name, e.g. 'monday', 'tuesday', etc.
            minutes: Minutes to add (can be negative to reduce).
        """
        day = day.lower()
        if day not in DAYS:
            raise ValueError(f"Invalid day {day!r}. Must be one of: {DAYS}")
        schedule = await self.get_schedule()
        current = schedule[day].allowance_minutes
        new_minutes = max(0, current + minutes)
        await self.set_allowance(day, minutes=new_minutes)

    async def add_allowance_today(self, *, minutes: int) -> None:
        """Add extra minutes to today's screen time allowance.

        Args:
            minutes: Minutes to add (can be negative to reduce).
        """
        from datetime import datetime
        today = datetime.now().strftime("%A").lower()
        await self.add_allowance(today, minutes=minutes)
