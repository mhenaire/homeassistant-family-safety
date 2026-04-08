"""DataUpdateCoordinator for Family Safety."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from pyfamilysafety2 import FamilySafety, Child, WeekSchedule
from pyfamilysafety2.exceptions import APIError, AuthExpiredError

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
                data[name] = {"child": child, "schedule": schedule}
            except APIError as err:
                _LOGGER.warning("Failed to fetch schedule for %s: %s", name, err)
                # Keep stale data if available
                if name in self.children:
                    data[name] = self.children[name]

        self.children = data
        return data
