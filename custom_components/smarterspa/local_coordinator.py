"""Push coordinator for the local controller. Event stream first, polling as a backstop."""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOCAL_FALLBACK_INTERVAL, LOCAL_NETWORK_INTERVAL
from .local_api import LocalApiError, LocalAuthError, LocalClient

_LOGGER = logging.getLogger(__name__)
RECONNECT_MAX = 60.0


class SmarterSpaLocalCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: LocalClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} local {entry.title}",
            update_interval=LOCAL_FALLBACK_INTERVAL,
        )
        self.client = client
        self.network: dict[str, Any] = {}
        self._network_at: datetime | None = None
        self._stream_task: asyncio.Task[None] | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            state = await self.client.get_state()
        except LocalAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except LocalApiError as err:
            raise UpdateFailed(str(err)) from err
        await self._refresh_network()
        return state

    async def _refresh_network(self) -> None:
        now = dt_util.utcnow()
        if self._network_at is not None and now - self._network_at < LOCAL_NETWORK_INTERVAL:
            return
        self._network_at = now
        try:
            self.network = await self.client.get_network()
        except LocalApiError as err:
            _LOGGER.debug("Network status unavailable: %s", err)

    # Event stream

    def start_stream(self) -> None:
        self._stream_task = self.config_entry.async_create_background_task(
            self.hass, self._stream(), f"{DOMAIN} event stream"
        )

    async def _stream(self) -> None:
        delay = 1.0
        while True:
            try:
                async for snapshot in self.client.events():
                    delay = 1.0
                    self.async_set_updated_data(snapshot)
            except LocalAuthError:
                self.config_entry.async_start_reauth(self.hass)
                return
            except (LocalApiError, OSError, TimeoutError, ValueError) as err:
                _LOGGER.debug("Event stream dropped: %s", err)
            except Exception:  # noqa: BLE001 - keep the stream alive whatever happens
                _LOGGER.exception("Event stream failed")
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX)

    # Commands

    async def async_run(self, action: str, **kwargs: Any) -> None:
        """Call a client method and apply the returned state straight away."""
        try:
            result = await getattr(self.client, action)(**kwargs)
        except LocalAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except LocalApiError as err:
            raise HomeAssistantError(f"SmarterSpa controller: {err}") from err
        if isinstance(result, dict) and "device_id" in result:
            self.async_set_updated_data(result)

    @property
    def device_id(self) -> str:
        return str(self.config_entry.unique_id or (self.data or {}).get("device_id") or "unknown")

    @property
    def firmware(self) -> str | None:
        version = (self.data or {}).get("version")
        return f"local {version}" if version else None
