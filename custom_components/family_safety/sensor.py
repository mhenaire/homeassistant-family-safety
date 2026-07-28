"""Sensor platform for Family Safety."""

from __future__ import annotations

import logging
from datetime import datetime

import voluptuous as vol

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .pyfamilysafety2.exceptions import APIError

from .const import (
    DOMAIN,
    SERVICE_SET_ALLOWANCE,
    SERVICE_ADD_ALLOWANCE,
    ATTR_CHILD,
    ATTR_DAY,
    ATTR_MINUTES,
    VALID_DAYS,
)
from .coordinator import FamilySafetyCoordinator

_VALID_DAY = vol.All(vol.Lower, vol.In(["today"] + VALID_DAYS))

_SERVICE_SET_ALLOWANCE_SCHEMA = vol.Schema({
    vol.Required(ATTR_CHILD): cv.string,
    vol.Optional(ATTR_DAY, default="today"): _VALID_DAY,
    vol.Required(ATTR_MINUTES): vol.All(vol.Coerce(int), vol.Range(min=0, max=1440)),
})

_SERVICE_ADD_ALLOWANCE_SCHEMA = vol.Schema({
    vol.Required(ATTR_CHILD): cv.string,
    vol.Optional(ATTR_DAY, default="today"): _VALID_DAY,
    vol.Required(ATTR_MINUTES): vol.All(vol.Coerce(int), vol.Range(min=-1440, max=1440)),
})

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors and register services."""
    coordinator: FamilySafetyCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for child_name in coordinator.data:
        entities.append(ScreenTimeAllowanceSensor(coordinator, child_name))
        entities.append(ScreenTimeUsedSensor(coordinator, child_name))
        entities.append(ScreenTimeUsedTodaySensor(coordinator, child_name))

    async_add_entities(entities)

    # Register services
    async def handle_set_allowance(call: ServiceCall) -> None:
        child_name = call.data[ATTR_CHILD]
        day = call.data.get(ATTR_DAY, "today")
        minutes = call.data[ATTR_MINUTES]

        if child_name not in coordinator.children:
            _LOGGER.error("Child %r not found", child_name)
            return

        child = coordinator.children[child_name]["child"]
        try:
            if day == "today":
                await child.set_allowance_today(minutes=minutes)
            else:
                await child.set_allowance(day, minutes=minutes)
            await coordinator.async_request_refresh()
        except APIError as err:
            _LOGGER.error("Failed to set allowance for %s: %s", child_name, err)

    async def handle_add_allowance(call: ServiceCall) -> None:
        child_name = call.data[ATTR_CHILD]
        day = call.data.get(ATTR_DAY, "today")
        minutes = call.data[ATTR_MINUTES]

        if child_name not in coordinator.children:
            _LOGGER.error("Child %r not found", child_name)
            return

        child = coordinator.children[child_name]["child"]
        try:
            if day == "today":
                await child.add_allowance_today(minutes=minutes)
            else:
                await child.add_allowance(day, minutes=minutes)
            await coordinator.async_request_refresh()
        except APIError as err:
            _LOGGER.error("Failed to add allowance for %s: %s", child_name, err)

    hass.services.async_register(DOMAIN, SERVICE_SET_ALLOWANCE, handle_set_allowance)
    hass.services.async_register(DOMAIN, SERVICE_ADD_ALLOWANCE, handle_add_allowance)


class ScreenTimeAllowanceSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing today's screen time allowance in minutes, with full week data as attributes."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0
    _attr_icon = "mdi:timer-outline"
    _attr_has_entity_name = True
    _attr_translation_key = "windows_allowance"

    def __init__(self, coordinator: FamilySafetyCoordinator, child_name: str) -> None:
        super().__init__(coordinator)
        self._child_name = child_name
        self._attr_unique_id = f"family_safety_{child_name.lower()}_windows_allowance"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, child_name.lower())},
            name=child_name,
            manufacturer="Microsoft",
            model="Family Safety",
        )

    @property
    def native_value(self) -> int | None:
        data = self.coordinator.data.get(self._child_name)
        if not data:
            return None
        today = datetime.now().strftime("%A").lower()
        try:
            return data["schedule"][today].allowance_minutes
        except KeyError:
            return None

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data.get(self._child_name)
        if not data:
            return {}
        schedule = data["schedule"]
        attrs = {}
        for day_schedule in schedule:
            attrs[f"{day_schedule.day}_allowance_minutes"] = day_schedule.allowance_minutes
            attrs[f"{day_schedule.day}_window_start"] = day_schedule.window_start.strftime("%H:%M")
            attrs[f"{day_schedule.day}_window_end"] = day_schedule.window_end.strftime("%H:%M")
        return attrs


class ScreenTimeUsedSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing actual screen time used over the last 7 days.

    The state is the total minutes used in the rolling 7-day window. Per-day
    usage is exposed as attributes (both a ``daily`` list keyed by date and
    convenient ``<weekday>_used_minutes`` keys) so it can drive a histogram
    chart in the dashboard.
    """

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0
    _attr_icon = "mdi:chart-bar"
    _attr_has_entity_name = True
    _attr_translation_key = "screen_time_used"

    def __init__(self, coordinator: FamilySafetyCoordinator, child_name: str) -> None:
        super().__init__(coordinator)
        self._child_name = child_name
        self._attr_unique_id = f"family_safety_{child_name.lower()}_screen_time_used"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, child_name.lower())},
            name=child_name,
            manufacturer="Microsoft",
            model="Family Safety",
        )

    @property
    def native_value(self) -> int | None:
        data = self.coordinator.data.get(self._child_name)
        if not data:
            return None
        usage = data.get("usage")
        if usage is None:
            return None
        return usage.total_minutes

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data.get(self._child_name)
        if not data:
            return {}
        usage = data.get("usage")
        if usage is None:
            return {}
        attrs: dict = {
            "daily_average_minutes": usage.daily_average_minutes,
            "total_hours": round(usage.total_hours, 2),
            "days_in_range": len(usage.days),
        }
        daily = []
        for day_usage in usage.days:
            iso = day_usage.day.isoformat()
            daily.append({"date": iso, "minutes": day_usage.used_minutes})
            attrs[f"{day_usage.day_name}_used_minutes"] = day_usage.used_minutes
        attrs["daily"] = daily
        return attrs


class ScreenTimeUsedTodaySensor(CoordinatorEntity, SensorEntity):
    """Sensor showing actual screen time used so far today (in minutes).

    Reuses the weekly usage data already fetched by the coordinator (no extra
    API call) and picks out today's entry.
    """

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0
    _attr_icon = "mdi:timer-sand"
    _attr_has_entity_name = True
    _attr_translation_key = "screen_time_used_today"

    def __init__(self, coordinator: FamilySafetyCoordinator, child_name: str) -> None:
        super().__init__(coordinator)
        self._child_name = child_name
        self._attr_unique_id = f"family_safety_{child_name.lower()}_screen_time_used_today"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, child_name.lower())},
            name=child_name,
            manufacturer="Microsoft",
            model="Family Safety",
        )

    def _today_usage(self):
        data = self.coordinator.data.get(self._child_name)
        if not data:
            return None
        usage = data.get("usage")
        if usage is None:
            return None
        today = datetime.now().date()
        for day_usage in usage.days:
            if day_usage.day == today:
                return day_usage
        return None

    @property
    def native_value(self) -> int | None:
        day_usage = self._today_usage()
        if day_usage is None:
            return None
        return day_usage.used_minutes

    @property
    def extra_state_attributes(self) -> dict:
        day_usage = self._today_usage()
        if day_usage is None:
            return {}
        return {"date": day_usage.day.isoformat()}
