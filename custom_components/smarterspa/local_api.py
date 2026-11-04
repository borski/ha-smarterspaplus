"""Client for the smarterspa-local controller's REST API and event stream."""

from __future__ import annotations

from collections.abc import AsyncIterator
import json
from typing import Any

import aiohttp

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)
STREAM_TIMEOUT = aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=45)


class LocalAuthError(Exception):
    """The controller rejected the API token."""


class LocalApiError(Exception):
    """The controller couldn't be reached or returned an error."""


class LocalClient:
    def __init__(self, session: aiohttp.ClientSession, host: str, port: int, token: str) -> None:
        self._session = session
        self._base = f"http://{host}:{port}/api/v1"
        self._headers = {"Authorization": f"Bearer {token}"}

    async def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        try:
            async with self._session.request(
                method, f"{self._base}{path}", headers=self._headers, json=body, timeout=REQUEST_TIMEOUT
            ) as response:
                if response.status == 401:
                    raise LocalAuthError("API token rejected")
                payload = await response.json(content_type=None)
                if response.status >= 400:
                    message = payload.get("error") if isinstance(payload, dict) else None
                    raise LocalApiError(message or f"HTTP {response.status}")
                return payload
        except (aiohttp.ClientError, TimeoutError, json.JSONDecodeError) as err:
            raise LocalApiError(str(err) or type(err).__name__) from err

    async def get_state(self) -> dict[str, Any]:
        return await self._request("GET", "/state")

    async def get_network(self) -> dict[str, Any]:
        return await self._request("GET", "/network")

    async def update_settings(self, **settings: Any) -> dict[str, Any]:
        return await self._request("PATCH", "/settings", settings)

    async def start_cycle(self) -> dict[str, Any]:
        return await self._request("POST", "/cycle/start")

    async def stop_cycle(self) -> dict[str, Any]:
        return await self._request("POST", "/cycle/stop")

    async def reset_electrode(self) -> dict[str, Any]:
        return await self._request("POST", "/electrode/reset")

    async def reboot(self) -> None:
        await self._request("POST", "/system/reboot")

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        """Yield state snapshots from the server sent event stream until it ends."""
        try:
            async for snapshot in self._events():
                yield snapshot
        except (aiohttp.ClientError, TimeoutError) as err:
            raise LocalApiError(str(err) or type(err).__name__) from err

    async def _events(self) -> AsyncIterator[dict[str, Any]]:
        async with self._session.get(
            f"{self._base}/events", headers=self._headers, timeout=STREAM_TIMEOUT
        ) as response:
            if response.status == 401:
                raise LocalAuthError("API token rejected")
            if response.status != 200:
                raise LocalApiError(f"HTTP {response.status}")
            event = ""
            data: list[str] = []
            async for raw in response.content:
                line = raw.decode().rstrip("\r\n")
                if not line:
                    if event == "state" and data:
                        yield json.loads("\n".join(data))
                    event, data = "", []
                elif line.startswith("event:"):
                    event = line[6:].strip()
                elif line.startswith("data:"):
                    data.append(line[5:].lstrip())
