"""Microsoft Family Safety integration for Home Assistant."""

from __future__ import annotations

import logging

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from pyfamilysafety2 import FamilySafety
from pyfamilysafety2.exceptions import AuthExpiredError, APIError

from .const import DOMAIN, PLATFORMS
from .coordinator import FamilySafetyCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Family Safety from a config entry."""
    session = async_get_clientsession(hass)

    tokens = entry.data.get("tokens")
    if not tokens:
        raise ConfigEntryAuthFailed("No tokens stored — please re-authenticate.")

    async def on_token_refresh(new_tokens: dict) -> None:
        """Persist refreshed tokens back to the config entry."""
        hass.config_entries.async_update_entry(entry, data={**entry.data, "tokens": new_tokens})

    try:
        fs = FamilySafety.from_tokens(tokens, session, on_token_refresh=on_token_refresh)
        # Eagerly refresh token to catch expiry at startup
        await fs._auth.refresh(session)
    except AuthExpiredError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except Exception as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = FamilySafetyCoordinator(hass, fs)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
