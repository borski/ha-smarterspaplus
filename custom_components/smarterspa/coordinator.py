"""Polling coordinator for SmarterSpa+."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import SmarterSpaApiError, SmarterSpaAuthError, SmarterSpaClient
from .const import DOMAIN, FAST_INTERVAL, FAST_WINDOW, NORMAL_INTERVAL

_LOGGER = logging.getLogger(__name__)


class SmarterSpaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the Firestore document. Speeds up briefly after a command."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: SmarterSpaClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=NORMAL_INTERVAL,
        )
        self.client = client
        self._fast_until: datetime | None = None
        # Last non-empty Feed reply, kept so a sensor can show it after the
        # device or app clears the field.
        self.last_feed: dict[str, Any] = {}

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.client.get_document()
        except SmarterSpaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SmarterSpaApiError as err:
            raise UpdateFailed(str(err)) from err

        feed = data.get("Feed")
        if isinstance(feed, dict) and feed:
            self.last_feed = dict(feed)

        now = dt_util.utcnow()
        if self._fast_until is not None and now >= self._fast_until:
            self._fast_until = None
            self.update_interval = NORMAL_INTERVAL
        return data

    async def async_send_command(self, command: str) -> None:
        """Write a command, then poll fast for a bit so the state catches up."""
        try:
            await self.client.send_command(command)
        except SmarterSpaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SmarterSpaApiError as err:
            raise UpdateFailed(str(err)) from err
        self._fast_until = dt_util.utcnow() + FAST_WINDOW
        self.update_interval = FAST_INTERVAL
        await self.async_request_refresh()

    # Convenience accessors used by the entities.

    @property
    def main(self) -> dict[str, Any]:
        return self.data.get("Main") or {} if self.data else {}

    @property
    def settings(self) -> dict[str, Any]:
        return self.data.get("Settings") or {} if self.data else {}

    @property
    def passport(self) -> dict[str, Any]:
        return self.data.get("Pass") or {} if self.data else {}

    @property
    def device_id(self) -> str:
        return str(self.passport.get("m") or self.config_entry.unique_id or "unknown")

    @property
    def firmware(self) -> str | None:
        value = self.passport.get("v")
        return str(value) if value is not None else None
