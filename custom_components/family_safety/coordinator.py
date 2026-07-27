"""DataUpdateCoordinator for Family Safety."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .pyfamilysafety2 import FamilySafety, Child, WeekSchedule
from .pyfamilysafety2.exceptions import APIError, AuthExpiredError

from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class FamilySafetyCoordinator(DataUpdateCoordinator):
    """Fetches and caches data for all children."""

    def __init__(self, hass: HomeAssistant, fs: FamilySafety) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.fs = fs
        # {child_name: {"child": Child, "schedule": WeekSchedule}}
        self.children: dict[str, dict] = {}

    async def _async_update_data(self) -> dict:
        """Fetch latest schedules for all children."""
        try:
            children = await self.fs.get_children()
        except AuthExpiredError as err:
            raise UpdateFailed(f"Authentication expired: {err}") from err
        except APIError as err:
            raise UpdateFailed(f"API error: {err}") from err

        data = {}
        for name, child in children.items():
            try:
                schedule = await child.get_schedule()
                entry = {"child": child, "schedule": schedule}
                # Usage (activity report) is optional — it only populates when
                # activity reporting is enabled, so failures here shouldn't drop
                # the schedule data.
                try:
                    entry["usage"] = await child.get_weekly_usage()
                except APIError as usage_err:
                    _LOGGER.debug("No usage data for %s: %s", name, usage_err)
                    # Preserve previous usage if we had it
                    prev = self.children.get(name)
                    if prev and prev.get("usage") is not None:
                        entry["usage"] = prev["usage"]
                    else:
                        entry["usage"] = None
                data[name] = entry
            except APIError as err:
                _LOGGER.warning("Failed to fetch schedule for %s: %s", name, err)
                # Keep stale data if available
                if name in self.children:
                    data[name] = self.children[name]

        self.children = data
        return data
