"""Firebase Auth + Firestore REST client for SmarterSpa+.

Reads: GET the device document (reference 3.3).
Writes: PATCH the Input field only (reference 3.5).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import aiohttp

from .const import ALLOWED_COMMANDS, REFRESH_URL, SIGNIN_URL, TOKEN_REFRESH_MARGIN, document_url

_LOGGER = logging.getLogger(__name__)


class SmarterSpaAuthError(Exception):
    """Sign-in or token refresh was rejected."""


class SmarterSpaApiError(Exception):
    """Firestore request failed."""


def _flatten(value: dict[str, Any]) -> Any:
    """Turn a Firestore REST value into plain Python."""
    if "mapValue" in value:
        fields = value["mapValue"].get("fields") or {}
        return {k: _flatten(v) for k, v in fields.items()}
    if "integerValue" in value:
        return int(value["integerValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "booleanValue" in value:
        return bool(value["booleanValue"])
    if "stringValue" in value:
        return value["stringValue"]
    if "timestampValue" in value:
        return value["timestampValue"]
    if "nullValue" in value:
        return None
    if "arrayValue" in value:
        return [_flatten(v) for v in value["arrayValue"].get("values") or []]
    return value


def parse_boot_time(raw: str | None) -> datetime | None:
    """Pass.t is 'YYYY-MM-DD HH:MM:SS.ffffff' in UTC with no zone suffix."""
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


class SmarterSpaClient:
    """Thin async client. One instance per config entry."""

    def __init__(self, session: aiohttp.ClientSession, email: str, password: str) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._id_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float = 0.0
        self.uid: str | None = None

    # ---- auth -------------------------------------------------------

    async def sign_in(self) -> str:
        """Email/password sign-in. Returns the uid."""
        body = {"email": self._email, "password": self._password, "returnSecureToken": True}
        async with self._session.post(SIGNIN_URL, json=body, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            data = await resp.json(content_type=None)
            if resp.status != 200:
                msg = (data.get("error") or {}).get("message", f"HTTP {resp.status}")
                raise SmarterSpaAuthError(msg)
        self._store_tokens(data["idToken"], data["refreshToken"], int(data.get("expiresIn", 3600)))
        self.uid = data["localId"]
        return self.uid

    async def _refresh(self) -> None:
        """Reference 3.2. Standard Firebase refresh, form encoded."""
        if not self._refresh_token:
            await self.sign_in()
            return
        form = {"grant_type": "refresh_token", "refresh_token": self._refresh_token}
        async with self._session.post(REFRESH_URL, data=form, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            data = await resp.json(content_type=None)
            if resp.status != 200:
                _LOGGER.debug("token refresh rejected (%s), signing in again", resp.status)
                await self.sign_in()
                return
        self._store_tokens(data["id_token"], data["refresh_token"], int(data.get("expires_in", 3600)))
        if not self.uid:
            self.uid = data.get("user_id")

    def _store_tokens(self, id_token: str, refresh_token: str, expires_in: int) -> None:
        self._id_token = id_token
        self._refresh_token = refresh_token
        self._expires_at = time.monotonic() + expires_in

    async def _token(self) -> str:
        if not self._id_token:
            await self.sign_in()
        elif time.monotonic() >= self._expires_at - TOKEN_REFRESH_MARGIN.total_seconds():
            await self._refresh()
        assert self._id_token is not None
        return self._id_token

    # ---- firestore --------------------------------------------------

    async def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        token = await self._token()
        headers = {"Authorization": f"Bearer {token}"}
        async with self._session.request(
            method, url, headers=headers, timeout=aiohttp.ClientTimeout(total=20), **kwargs
        ) as resp:
            if resp.status == 401:
                # Token went stale under us. One retry after a fresh sign-in.
                await self.sign_in()
                headers["Authorization"] = f"Bearer {self._id_token}"
                async with self._session.request(
                    method, url, headers=headers, timeout=aiohttp.ClientTimeout(total=20), **kwargs
                ) as retry:
                    if retry.status != 200:
                        raise SmarterSpaApiError(f"{method} {url} -> HTTP {retry.status}")
                    return await retry.json(content_type=None)
            if resp.status != 200:
                text = await resp.text()
                raise SmarterSpaApiError(f"{method} {url} -> HTTP {resp.status}: {text[:200]}")
            return await resp.json(content_type=None)

    async def get_document(self) -> dict[str, Any]:
        """Return the device document flattened to plain dicts."""
        if not self.uid:
            await self.sign_in()
        assert self.uid is not None
        raw = await self._request("GET", document_url(self.uid))
        fields = raw.get("fields") or {}
        data = {k: _flatten(v) for k, v in fields.items()}
        data["_update_time"] = raw.get("updateTime")
        return data

    async def send_command(self, command: str) -> None:
        """Reference 3.5. PATCH only the Input field."""
        if command not in ALLOWED_COMMANDS:
            raise ValueError("Unsupported SmarterSpa command")
        if not self.uid:
            await self.sign_in()
        assert self.uid is not None
        url = document_url(self.uid) + "?updateMask.fieldPaths=Input"
        body = {"fields": {"Input": {"stringValue": command}}}
        _LOGGER.debug("sending command %r", command)
        await self._request("PATCH", url, json=body)
