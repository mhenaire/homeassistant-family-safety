"""Top-level FamilySafety API class."""

from __future__ import annotations

from typing import Any, Callable, Coroutine

import aiohttp

from .auth import Authenticator, DeviceCodeInfo, OnTokenRefreshCallback, TokenStore
from .client import FamilySafetyClient
from .models import Child, WeekSchedule


class FamilySafety:
    """Main entry point for the pyfamilysafety2 library.

    Usage (device code flow — first time):
        async with aiohttp.ClientSession() as session:
            code = await FamilySafety.start_device_auth(session)
            print(f"Go to {code.verification_uri} and enter {code.user_code}")
            fs = await FamilySafety.wait_for_device_auth(session, code)
            tokens = fs.get_tokens()  # save these

    Usage (subsequent runs):
        async with aiohttp.ClientSession() as session:
            fs = FamilySafety.from_tokens(tokens, session)
            children = await fs.get_children()
    """

    def __init__(
        self,
        auth: Authenticator,
        session: aiohttp.ClientSession,
        *,
        owns_session: bool = False,
    ) -> None:
        self._auth = auth
        self._session = session
        self._owns_session = owns_session
        self._client = FamilySafetyClient(auth, session)

    async def __aenter__(self) -> "FamilySafety":
        return self

    async def __aexit__(self, *args) -> None:
        if self._owns_session:
            await self._session.close()

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    @classmethod
    async def start_device_auth(
        cls, session: aiohttp.ClientSession
    ) -> DeviceCodeInfo:
        """Request a device code. Show user_code + verification_uri to the user."""
        return await Authenticator.start_device_auth(session)

    @classmethod
    async def poll_device_auth(
        cls,
        session: aiohttp.ClientSession,
        device_code_info: DeviceCodeInfo,
        on_token_refresh: OnTokenRefreshCallback | None = None,
    ) -> "FamilySafety":
        """Poll once for token. Raises AuthPendingError if not yet approved.

        Use this in HA config flow where you control the polling loop.
        """
        auth = await Authenticator.poll_device_auth(
            session, device_code_info, on_token_refresh
        )
        return cls(auth, session)

    @classmethod
    async def wait_for_device_auth(
        cls,
        session: aiohttp.ClientSession,
        device_code_info: DeviceCodeInfo,
        on_token_refresh: OnTokenRefreshCallback | None = None,
    ) -> "FamilySafety":
        """Block until the user approves the device code (for CLI scripts)."""
        auth = await Authenticator.wait_for_device_auth(
            session, device_code_info, on_token_refresh
        )
        return cls(auth, session)

    @classmethod
    def from_tokens(
        cls,
        tokens: TokenStore,
        session: aiohttp.ClientSession,
        on_token_refresh: OnTokenRefreshCallback | None = None,
    ) -> "FamilySafety":
        """Create a FamilySafety instance from previously saved tokens."""
        auth = Authenticator.from_tokens(tokens, on_token_refresh)
        return cls(auth, session)

    def get_tokens(self) -> TokenStore:
        """Return the current tokens (save these for next time)."""
        return self._auth.get_tokens()

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    async def get_children(self) -> dict[str, Child]:
        """Return a dict of {first_name: Child} for all children in the family."""
        children = await self._client.get_children()
        return {c.first_name: c for c in children}

    async def get_child(self, name: str) -> Child:
        """Get a specific child by first name."""
        children = await self.get_children()
        if name not in children:
            raise KeyError(f"No child named {name!r}. Available: {list(children.keys())}")
        return children[name]
