"""Tests for pyfamilysafety2 client module."""

import pytest
from datetime import time
from unittest.mock import AsyncMock, MagicMock

import aiohttp
from aioresponses import aioresponses

from pyfamilysafety2.auth import Authenticator
from pyfamilysafety2.client import FamilySafetyClient, _BASE_URL
from pyfamilysafety2.models import WeekSchedule
from pyfamilysafety2.exceptions import APIError

FAKE_TOKENS = {
    "access_token": "fake-access-token",
    "refresh_token": "fake-refresh-token",
}

FAKE_ROSTER = {
    "members": [
        {
            "id": 100000000000001,
            "role": "Admin",
            "user": {"id": 100000000000001, "firstName": "Parent", "safeDisplayName": "Parent Account", "ageGroup": "Adult"},
        },
        {
            "id": 200000000000001,
            "role": "User",
            "user": {"id": 200000000000001, "firstName": "Child", "safeDisplayName": "Child Account", "ageGroup": "NotAdult"},
        },
    ]
}

FAKE_SCHEDULE = {
    "mode": "PerDeviceType",
    "schedules": [
        {
            "appliesTo": "Windows",
            "enabled": True,
            "dailyRestrictions": {
                "monday": {"allowance": 0, "allottedIntervals": [{"begin": "09:00:00", "end": "21:00:00"}]},
                "tuesday": {"allowance": 0, "allottedIntervals": [{"begin": "09:00:00", "end": "21:00:00"}]},
                "wednesday": {"allowance": 0, "allottedIntervals": [{"begin": "09:00:00", "end": "21:00:00"}]},
                "thursday": {"allowance": 0, "allottedIntervals": [{"begin": "09:00:00", "end": "21:00:00"}]},
                "friday": {"allowance": 3600000, "allottedIntervals": [{"begin": "09:00:00", "end": "20:00:00"}]},
                "saturday": {"allowance": 7200000, "allottedIntervals": [{"begin": "09:00:00", "end": "20:00:00"}]},
                "sunday": {"allowance": 7200000, "allottedIntervals": [{"begin": "09:00:00", "end": "19:00:00"}]},
            },
        }
    ],
}


@pytest.fixture
def auth():
    return Authenticator.from_tokens(FAKE_TOKENS)


@pytest.mark.asyncio
async def test_get_children(auth):
    async with aiohttp.ClientSession() as session:
        client = FamilySafetyClient(auth, session)
        with aioresponses() as m:
            m.get(f"{_BASE_URL}/v2/roster", payload=FAKE_ROSTER)
            children = await client.get_children()
        assert len(children) == 1
        assert children[0].first_name == "Child"
        assert children[0].user_id == "200000000000001"


@pytest.mark.asyncio
async def test_get_schedule(auth):
    async with aiohttp.ClientSession() as session:
        client = FamilySafetyClient(auth, session)
        with aioresponses() as m:
            # Match any URL starting with the schedule endpoint (ignore query params)
            import re
            m.get(
                re.compile(rf"{re.escape(_BASE_URL)}/v4/devicelimits/schedules/200000000000001.*"),
                payload=FAKE_SCHEDULE,
            )
            schedule = await client.get_schedule("200000000000001")
        assert isinstance(schedule, WeekSchedule)
        assert schedule["friday"].allowance_minutes == 60
        assert schedule["saturday"].allowance_minutes == 120
        assert schedule["monday"].allowance_minutes == 0


@pytest.mark.asyncio
async def test_get_schedule_no_windows(auth):
    async with aiohttp.ClientSession() as session:
        client = FamilySafetyClient(auth, session)
        with aioresponses() as m:
            import re
            m.get(
                re.compile(rf"{re.escape(_BASE_URL)}/v4/devicelimits/schedules/200000000000001.*"),
                payload={"schedules": []},
            )
            with pytest.raises(APIError):
                await client.get_schedule("200000000000001")


@pytest.mark.asyncio
async def test_patch_schedule(auth):
    async with aiohttp.ClientSession() as session:
        client = FamilySafetyClient(auth, session)
        with aioresponses() as m:
            m.patch(
                f"{_BASE_URL}/v4/devicelimits/schedules/200000000000001",
                status=200,
                payload={},
            )
            # Should not raise
            await client.patch_schedule(
                "200000000000001",
                day="monday",
                allowance_minutes=30,
                window_start=time(9, 0),
                window_end=time(21, 0),
            )


@pytest.mark.asyncio
async def test_api_error_propagated(auth):
    async with aiohttp.ClientSession() as session:
        client = FamilySafetyClient(auth, session)
        with aioresponses() as m:
            m.get(f"{_BASE_URL}/v2/roster", status=500, payload={"error": {"message": "Server error"}})
            with pytest.raises(APIError) as exc_info:
                await client.get_children()
            assert exc_info.value.status == 500
