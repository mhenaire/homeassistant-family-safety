"""Config flow for Microsoft Family Safety."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .pyfamilysafety2 import FamilySafety
from .pyfamilysafety2.auth import DeviceCodeInfo
from .pyfamilysafety2.exceptions import AuthPendingError, AuthExpiredError, AuthError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class FamilySafetyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Microsoft Family Safety."""

    VERSION = 1

    def __init__(self) -> None:
        self._device_code_info: DeviceCodeInfo | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start device code flow and show the code to the user."""
        errors: dict[str, str] = {}
        session = async_get_clientsession(self.hass)

        if user_input is not None and self._device_code_info is not None:
            # User clicked Submit — try to get the token
            try:
                fs = await FamilySafety.poll_device_auth(
                    session, self._device_code_info
                )
                tokens = fs.get_tokens()
                return self.async_create_entry(
                    title="Microsoft Family Safety",
                    data={"tokens": tokens},
                )
            except AuthPendingError:
                errors["base"] = "auth_pending"
            except AuthExpiredError:
                errors["base"] = "auth_expired"
                self._device_code_info = None
            except AuthError:
                errors["base"] = "auth_failed"

        # Fetch a new device code if we don't have one (or it expired)
        if self._device_code_info is None:
            try:
                self._device_code_info = await FamilySafety.start_device_auth(session)
            except AuthError as err:
                _LOGGER.error("Failed to start device auth: %s", err)
                return self.async_abort(reason="auth_failed")

        info = self._device_code_info
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            description_placeholders={
                "url": info.verification_uri,
                "code": info.user_code,
                "expires_in": str(info.expires_in // 60),
            },
            errors=errors,
        )

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Re-authentication step when tokens expire."""
        return await self.async_step_user(user_input)

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Re-authentication step when tokens expire."""
        return await self.async_step_user()
