"""HTTP client for the Microsoft Family Safety mobile aggregator API."""

from __future__ import annotations

from datetime import datetime, timezone
from datetime import time as dtime
from typing import Any
from urllib.parse import urlencode

import aiohttp

from .auth import Authenticator
from .exceptions import APIError, AuthExpiredError
from .models import Child, WeekSchedule

_BASE_URL = "https://mobileaggregator.family.microsoft.com/api"
_USER_AGENT = "iOS/26.4 iPhone17,1"
_CULTURE = "en-us"

_MS_PER_MINUTE = 60_000


def _now_iso() -> str:
    """Current local time as ISO 8601 with UTC offset, as expected by the API."""
    now = datetime.now().astimezone()
    return now.strftime("%Y-%m-%dT%H:%M:%S") + now.strftime("%z")[:3] + ":" + now.strftime("%z")[3:]


class FamilySafetyClient:
    """Low-level async HTTP client for the Family Safety mobile aggregator API."""

    def __init__(self, auth: Authenticator, session: aiohttp.ClientSession) -> None:
        self._auth = auth
        self._session = session

    def _headers(self, plat_info: str | None = None) -> dict[str, str]:
        h = {
            "Authorization": self._auth.auth_header,
            "User-Agent": _USER_AGENT,
            "Accept": "application/json",
        }
        if plat_info:
            h["Plat-Info"] = plat_info
        return h

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json: Any = None,
        plat_info: str | None = None,
        retry_on_401: bool = True,
    ) -> Any:
        url = f"{_BASE_URL}/{path}"
        async with self._session.request(
            method,
            url,
            params=params,
            json=json,
            headers=self._headers(plat_info),
        ) as resp:
            if resp.status == 401 and retry_on_401:
                # Token expired — refresh and retry once
                await self._auth.refresh(self._session)
                return await self._request(
                    method, path, params=params, json=json,
                    plat_info=plat_info, retry_on_401=False
                )
            if resp.status == 204 or resp.content_length == 0:
                return None
            data = await resp.json(content_type=None)
            if resp.status >= 400:
                msg = data.get("error", {}).get("message", str(data)) if isinstance(data, dict) else str(data)
                raise APIError(resp.status, msg)
            return data

    async def get_roster(self) -> list[dict]:
        """Return raw roster member list."""
        data = await self._request("GET", "v2/roster")
        return data.get("members", [])

    async def get_children(self) -> list[Child]:
        """Return Child objects for minor family members (ageGroup == 'NotAdult').

        Adult members are excluded even if their role is 'User' — the schedule
        write endpoint returns 500 for adult accounts.
        """
        members = await self.get_roster()
        children = []
        for m in members:
            user = m.get("user", {})
            # Only include minor (child) accounts
            if user.get("ageGroup", "").lower() != "notadult":
                continue
            # user id is at top level as "id"
            puid = m.get("id") or user.get("id")
            if not puid:
                continue
            children.append(Child(
                user_id=str(puid),
                first_name=user.get("firstName", ""),
                display_name=user.get("safeDisplayName") or user.get("firstName", ""),
                _client=self,
            ))
        return children

    async def get_schedule(self, user_id: str) -> WeekSchedule:
        """Fetch Windows screen time schedule for a child."""
        now = _now_iso()
        data = await self._request(
            "GET",
            f"v4/devicelimits/schedules/{user_id}",
            params={"culture": _CULTURE, "time": now},
            plat_info="Windows",
        )
        if data is None:
            raise APIError(200, f"No schedule data returned for user {user_id}")

        # Find the Windows schedule
        schedules = data.get("schedules", [])
        windows_schedule = next(
            (s for s in schedules if s.get("appliesTo") == "Windows"),
            None,
        )
        if windows_schedule is None:
            raise APIError(200, "No Windows schedule found in response")

        return WeekSchedule._from_api(windows_schedule.get("dailyRestrictions", {}))

    async def patch_schedule(
        self,
        user_id: str,
        *,
        day: str,
        allowance_minutes: int,
        window_start: dtime,
        window_end: dtime,
    ) -> None:
        """Patch a single day's Windows screen time schedule."""
        now = _now_iso()
        payload = {
            "culture": _CULTURE,
            "time": now,
            "appliesTo": "Windows",
            "mode": "PerDeviceType",
            "dailyRestrictions": {
                day: {
                    "allowance": allowance_minutes * _MS_PER_MINUTE,
                    "allottedIntervals": [
                        {
                            "begin": window_start.strftime("%H:%M:%S"),
                            "end": window_end.strftime("%H:%M:%S"),
                        }
                    ],
                }
            },
        }
        await self._request(
            "PATCH",
            f"v4/devicelimits/schedules/{user_id}?",
            json=payload,
            plat_info="Windows",
        )
