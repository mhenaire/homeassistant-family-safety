"""Tests for pyfamilysafety2 models."""

import pytest
from datetime import time

from pyfamilysafety2.models import DaySchedule, WeekSchedule, DAYS


class TestDaySchedule:
    def test_from_api_basic(self):
        data = {
            "allowance": 3600000,  # 60 minutes
            "allottedIntervals": [{"begin": "09:00:00", "end": "21:00:00"}],
        }
        day = DaySchedule._from_api("monday", data)
        assert day.day == "monday"
        assert day.allowance_minutes == 60
        assert day.window_start == time(9, 0)
        assert day.window_end == time(21, 0)
        assert day.limit_enabled is True

    def test_from_api_zero_allowance(self):
        data = {
            "allowance": 0,
            "allottedIntervals": [{"begin": "09:00:00", "end": "21:00:00"}],
        }
        day = DaySchedule._from_api("monday", data)
        assert day.allowance_minutes == 0
        assert day.limit_enabled is False

    def test_from_api_no_intervals(self):
        data = {"allowance": 1800000, "allottedIntervals": []}
        day = DaySchedule._from_api("friday", data)
        assert day.allowance_minutes == 30
        assert day.window_start == time(0, 0)
        assert day.window_end == time(23, 59)

    def test_allowance_hours(self):
        data = {
            "allowance": 7200000,  # 120 minutes = 2 hours
            "allottedIntervals": [{"begin": "09:00:00", "end": "20:00:00"}],
        }
        day = DaySchedule._from_api("saturday", data)
        assert day.allowance_hours == 2.0

    def test_to_patch_payload(self):
        day = DaySchedule(
            day="monday",
            allowance_minutes=90,
            window_start=time(9, 0),
            window_end=time(21, 0),
            limit_enabled=True,
        )
        payload = day._to_patch_payload()
        assert payload["allowance"] == 5_400_000  # 90 * 60_000
        assert payload["allottedIntervals"][0]["begin"] == "09:00:00"
        assert payload["allottedIntervals"][0]["end"] == "21:00:00"

    def test_repr(self):
        day = DaySchedule(
            day="monday",
            allowance_minutes=60,
            window_start=time(9, 0),
            window_end=time(21, 0),
            limit_enabled=True,
        )
        assert "monday" in repr(day)
        assert "60min" in repr(day)


class TestWeekSchedule:
    def _make_schedule(self):
        raw = {
            "monday": {"allowance": 0, "allottedIntervals": [{"begin": "09:00:00", "end": "21:00:00"}]},
            "tuesday": {"allowance": 0, "allottedIntervals": [{"begin": "09:00:00", "end": "21:00:00"}]},
            "wednesday": {"allowance": 0, "allottedIntervals": [{"begin": "09:00:00", "end": "21:00:00"}]},
            "thursday": {"allowance": 0, "allottedIntervals": [{"begin": "09:00:00", "end": "21:00:00"}]},
            "friday": {"allowance": 3600000, "allottedIntervals": [{"begin": "09:00:00", "end": "20:00:00"}]},
            "saturday": {"allowance": 7200000, "allottedIntervals": [{"begin": "09:00:00", "end": "20:00:00"}]},
            "sunday": {"allowance": 7200000, "allottedIntervals": [{"begin": "09:00:00", "end": "19:00:00"}]},
        }
        return WeekSchedule._from_api(raw)

    def test_from_api(self):
        schedule = self._make_schedule()
        assert len(schedule.days) == 7
        assert schedule["monday"].allowance_minutes == 0
        assert schedule["friday"].allowance_minutes == 60
        assert schedule["saturday"].allowance_minutes == 120

    def test_getitem_case_insensitive(self):
        schedule = self._make_schedule()
        assert schedule["Monday"].allowance_minutes == 0
        assert schedule["FRIDAY"].allowance_minutes == 60

    def test_iteration(self):
        schedule = self._make_schedule()
        days = list(schedule)
        assert len(days) == 7
        assert all(isinstance(d, DaySchedule) for d in days)

    def test_items(self):
        schedule = self._make_schedule()
        items = dict(schedule.items())
        assert "friday" in items
        assert items["friday"].allowance_minutes == 60
