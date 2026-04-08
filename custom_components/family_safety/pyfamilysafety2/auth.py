"""Authentication for pyfamilysafety2.

Implements Microsoft Live device code flow for the Family Safety mobile aggregator API.
Tokens are refreshable indefinitely as long as the refresh_token is used periodically.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine

import aiohttp

from .exceptions import AuthError, AuthExpiredError, AuthPendingError

_CLIENT_ID = "000000000004893A"
_SCOPE = "service::familymobile.microsoft.com::MBI_SSL"
_TOKEN_URL = "https://login.live.com/oauth20_token.srf"
_DEVICE_CODE_URL = "https://login.live.com/oauth20_connect.srf"
_USER_AGENT = "iOS/26.4 iPhone17,1"

TokenStore = dict[str, Any]
OnTokenRefreshCallback = Callable[[TokenStore], Coroutine[Any, Any, None]]


class DeviceCodeInfo:
    """Information returned from the device code request."""

    def __init__(self, data: dict) -> None:
        self.user_code: str = data["user_code"]
        self.device_code: str = data["device_code"]
        self.verification_uri: str = data["verification_uri"]
        self.expires_in: int = data["expires_in"]
        self.interval: int = data["interval"]

    def __repr__(self) -> str:
        return (
            f"DeviceCodeInfo(user_code={self.user_code!r}, "
            f"verification_uri={self.verification_uri!r}, "
            f"expires_in={self.expires_in}s)"
        )


class Authenticator:
    """Handles Microsoft Live OAuth2 device code flow and token refresh."""

    def __init__(
        self,
        tokens: TokenStore,
        on_token_refresh: OnTokenRefreshCallback | None = None,
    ) -> None:
        self._tokens = tokens
        self._on_token_refresh = on_token_refresh

    @property
    def access_token(self) -> str:
        return self._tokens["access_token"]

    @property
    def auth_header(self) -> str:
        return f'MSAuth1.0 usertoken="{self.access_token}", type="MSACT"'

    @classmethod
    async def start_device_auth(cls, session: aiohttp.ClientSession) -> DeviceCodeInfo:
        """Step 1: Request a device code. Show user_code and verification_uri to the user."""
        async with session.post(
            _DEVICE_CODE_URL,
            data={
                "client_id": _CLIENT_ID,
                "scope": _SCOPE,
                "response_type": "device_code",
            },
            headers={"User-Agent": _USER_AGENT},
        ) as resp:
            data = await resp.json(content_type=None)
            if resp.status != 200:
                raise AuthError(f"Failed to get device code: {data}")
            return DeviceCodeInfo(data)

    @classmethod
    async def poll_device_auth(
        cls,
        session: aiohttp.ClientSession,
        device_code_info: DeviceCodeInfo,
        on_token_refresh: OnTokenRefreshCallback | None = None,
    ) -> "Authenticator":
        """Step 2: Poll until the user approves the device code.

        Raises AuthPendingError if not yet approved, AuthExpiredError if expired.
        Call this in a loop with device_code_info.interval seconds between calls.
        """
        async with session.post(
            _TOKEN_URL,
            data={
                "client_id": _CLIENT_ID,
                "device_code": device_code_info.device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            headers={"User-Agent": _USER_AGENT},
        ) as resp:
            data = await resp.json(content_type=None)

        if "access_token" in data:
            return cls(data, on_token_refresh)

        error = data.get("error", "")
        if error == "authorization_pending":
            raise AuthPendingError("User has not yet approved the device code.")
        elif error in ("authorization_declined", "expired_token", "bad_verification_code"):
            raise AuthExpiredError(f"Device code flow failed: {error}")
        else:
            raise AuthError(f"Unexpected error during device auth polling: {data}")

    @classmethod
    async def wait_for_device_auth(
        cls,
        session: aiohttp.ClientSession,
        device_code_info: DeviceCodeInfo,
        on_token_refresh: OnTokenRefreshCallback | None = None,
    ) -> "Authenticator":
        """Poll until approved or expired. Blocks until done.

        Useful for CLI scripts. For HA config flow, use poll_device_auth directly.
        """
        deadline = asyncio.get_event_loop().time() + device_code_info.expires_in
        while asyncio.get_event_loop().time() < deadline:
            try:
                return await cls.poll_device_auth(session, device_code_info, on_token_refresh)
            except AuthPendingError:
                await asyncio.sleep(device_code_info.interval)
        raise AuthExpiredError("Device code expired before user approved.")

    @classmethod
    def from_tokens(
        cls,
        tokens: TokenStore,
        on_token_refresh: OnTokenRefreshCallback | None = None,
    ) -> "Authenticator":
        """Create an Authenticator from a previously saved token dict."""
        return cls(tokens, on_token_refresh)

    async def refresh(self, session: aiohttp.ClientSession) -> None:
        """Refresh the access token using the refresh token."""
        async with session.post(
            _TOKEN_URL,
            data={
                "client_id": _CLIENT_ID,
                "refresh_token": self._tokens["refresh_token"],
                "grant_type": "refresh_token",
                "scope": _SCOPE,
            },
            headers={"User-Agent": _USER_AGENT},
        ) as resp:
            data = await resp.json(content_type=None)

        if "access_token" not in data:
            error = data.get("error", "unknown")
            if error in ("invalid_grant", "expired_token"):
                raise AuthExpiredError("Refresh token is invalid or expired. Re-authentication required.")
            raise AuthError(f"Token refresh failed: {data}")

        self._tokens = data
        if self._on_token_refresh:
            await self._on_token_refresh(self._tokens)

    def get_tokens(self) -> TokenStore:
        """Return the current token dict (for saving to persistent storage)."""
        return dict(self._tokens)
