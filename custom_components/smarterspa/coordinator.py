"""Polling coordinator for SmarterSpa+."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import aiohttp

from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import SmarterSpaApiError, SmarterSpaAuthError, SmarterSpaClient
from .const import ALLOWED_COMMANDS, COMMAND_TARGETS, DOMAIN, FAST_INTERVAL, FAST_WINDOW, NORMAL_INTERVAL

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
        self._command_lock = asyncio.Lock()
        self._target: tuple[str, str, int] | None = None
        self._command_generation = 0
        # Last non-empty Feed reply, kept so a sensor can show it after the
        # device or app clears the field.
        self.last_feed: dict[str, Any] = {}

    async def _async_update_data(self) -> dict[str, Any]:
        generation = self._command_generation
        try:
            data = await self.client.get_document()
        except SmarterSpaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (SmarterSpaApiError, aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(str(err)) from err

        feed = data.get("Feed")
        if isinstance(feed, dict) and feed:
            self.last_feed = dict(feed)

        now = dt_util.utcnow()
        matched = False
        if self._target is not None and generation == self._command_generation:
            section, key, value = self._target
            matched = not data.get("Input") and (data.get(section) or {}).get(key) == value
        if self._fast_until is not None and (matched or now >= self._fast_until):
            self._fast_until = None
            self._target = None
            self.update_interval = NORMAL_INTERVAL
        return data

    async def async_send_command(self, command: str) -> None:
        """Reject overlapping commands and poll until state matches or time runs out."""
        if command not in ALLOWED_COMMANDS:
            raise HomeAssistantError("Unsupported SmarterSpa command")
        async with self._command_lock:
            if self._fast_until is not None and dt_util.utcnow() < self._fast_until:
                raise HomeAssistantError("A SmarterSpa command is still pending")
            try:
                data = await self.client.get_document()
                if data.get("Input"):
                    raise HomeAssistantError("The SmarterSpa command inbox is busy")
                self._command_generation += 1
                await self.client.send_command(command)
            except SmarterSpaAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except (SmarterSpaApiError, aiohttp.ClientError, TimeoutError) as err:
                raise HomeAssistantError("SmarterSpa command failed. Check state before retrying") from err
            self._target = COMMAND_TARGETS.get(command)
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
