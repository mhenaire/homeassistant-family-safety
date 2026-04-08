"""Tests for pyfamilysafety2 auth module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from aioresponses import aioresponses

from pyfamilysafety2.auth import Authenticator, DeviceCodeInfo, _DEVICE_CODE_URL, _TOKEN_URL
from pyfamilysafety2.exceptions import AuthError, AuthPendingError, AuthExpiredError

FAKE_DEVICE_CODE_RESPONSE = {
    "user_code": "ABC12345",
    "device_code": "fake-device-code",
    "verification_uri": "https://microsoft.com/link",
    "expires_in": 900,
    "interval": 5,
}

FAKE_TOKENS = {
    "access_token": "fake-access-token",
    "refresh_token": "fake-refresh-token",
    "token_type": "bearer",
    "expires_in": 86400,
}


class TestDeviceCodeInfo:
    def test_fields(self):
        info = DeviceCodeInfo(FAKE_DEVICE_CODE_RESPONSE)
        assert info.user_code == "ABC12345"
        assert info.device_code == "fake-device-code"
        assert info.verification_uri == "https://microsoft.com/link"
        assert info.expires_in == 900
        assert info.interval == 5

    def test_repr(self):
        info = DeviceCodeInfo(FAKE_DEVICE_CODE_RESPONSE)
        assert "ABC12345" in repr(info)


class TestAuthenticator:
    @pytest.mark.asyncio
    async def test_start_device_auth(self):
        async with aiohttp.ClientSession() as session:
            with aioresponses() as m:
                m.post(_DEVICE_CODE_URL, payload=FAKE_DEVICE_CODE_RESPONSE)
                info = await Authenticator.start_device_auth(session)
                assert info.user_code == "ABC12345"

    @pytest.mark.asyncio
    async def test_poll_device_auth_pending(self):
        async with aiohttp.ClientSession() as session:
            info = DeviceCodeInfo(FAKE_DEVICE_CODE_RESPONSE)
            with aioresponses() as m:
                m.post(_TOKEN_URL, payload={"error": "authorization_pending"})
                with pytest.raises(AuthPendingError):
                    await Authenticator.poll_device_auth(session, info)

    @pytest.mark.asyncio
    async def test_poll_device_auth_success(self):
        async with aiohttp.ClientSession() as session:
            info = DeviceCodeInfo(FAKE_DEVICE_CODE_RESPONSE)
            with aioresponses() as m:
                m.post(_TOKEN_URL, payload=FAKE_TOKENS)
                auth = await Authenticator.poll_device_auth(session, info)
                assert auth.access_token == "fake-access-token"

    @pytest.mark.asyncio
    async def test_poll_device_auth_expired(self):
        async with aiohttp.ClientSession() as session:
            info = DeviceCodeInfo(FAKE_DEVICE_CODE_RESPONSE)
            with aioresponses() as m:
                m.post(_TOKEN_URL, payload={"error": "expired_token"})
                with pytest.raises(AuthExpiredError):
                    await Authenticator.poll_device_auth(session, info)

    @pytest.mark.asyncio
    async def test_refresh_success(self):
        auth = Authenticator.from_tokens(FAKE_TOKENS)
        async with aiohttp.ClientSession() as session:
            new_tokens = {**FAKE_TOKENS, "access_token": "new-access-token"}
            with aioresponses() as m:
                m.post(_TOKEN_URL, payload=new_tokens)
                await auth.refresh(session)
                assert auth.access_token == "new-access-token"

    @pytest.mark.asyncio
    async def test_refresh_calls_callback(self):
        callback = AsyncMock()
        auth = Authenticator.from_tokens(FAKE_TOKENS, on_token_refresh=callback)
        async with aiohttp.ClientSession() as session:
            new_tokens = {**FAKE_TOKENS, "access_token": "new-access-token"}
            with aioresponses() as m:
                m.post(_TOKEN_URL, payload=new_tokens)
                await auth.refresh(session)
                callback.assert_called_once_with(new_tokens)

    @pytest.mark.asyncio
    async def test_refresh_expired(self):
        auth = Authenticator.from_tokens(FAKE_TOKENS)
        async with aiohttp.ClientSession() as session:
            with aioresponses() as m:
                m.post(_TOKEN_URL, payload={"error": "invalid_grant"})
                with pytest.raises(AuthExpiredError):
                    await auth.refresh(session)

    def test_auth_header(self):
        auth = Authenticator.from_tokens(FAKE_TOKENS)
        assert 'MSAuth1.0 usertoken="fake-access-token"' in auth.auth_header

    def test_get_tokens(self):
        auth = Authenticator.from_tokens(FAKE_TOKENS)
        tokens = auth.get_tokens()
        assert tokens["access_token"] == "fake-access-token"
        assert tokens["refresh_token"] == "fake-refresh-token"
