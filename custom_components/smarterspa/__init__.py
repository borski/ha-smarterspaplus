"""SmarterSpa+ (ControlOMatic). Vendor cloud or the local replacement controller."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_HOST, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SmarterSpaApiError, SmarterSpaAuthError, SmarterSpaClient
from .const import CONF_CONNECTION, CONF_TOKEN, CONNECTION_LOCAL
from .coordinator import SmarterSpaCoordinator
from .local_api import LocalClient
from .local_coordinator import SmarterSpaLocalCoordinator

CLOUD_PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH, Platform.NUMBER, Platform.BUTTON]
LOCAL_PLATFORMS: list[Platform] = [*CLOUD_PLATFORMS, Platform.BINARY_SENSOR, Platform.SELECT]

SmarterSpaConfigEntry = ConfigEntry[Any]


def is_local(entry: ConfigEntry) -> bool:
    return entry.data.get(CONF_CONNECTION) == CONNECTION_LOCAL


def _platforms(entry: ConfigEntry) -> list[Platform]:
    return LOCAL_PLATFORMS if is_local(entry) else CLOUD_PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: SmarterSpaConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    if is_local(entry):
        client = LocalClient(session, entry.data[CONF_HOST], entry.data[CONF_PORT], entry.data[CONF_TOKEN])
        local = SmarterSpaLocalCoordinator(hass, entry, client)
        await local.async_config_entry_first_refresh()
        entry.runtime_data = local
        await hass.config_entries.async_forward_entry_setups(entry, LOCAL_PLATFORMS)
        local.start_stream()
        return True

    cloud_client = SmarterSpaClient(session, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
    try:
        await cloud_client.sign_in()
    except SmarterSpaAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except SmarterSpaApiError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = SmarterSpaCoordinator(hass, entry, cloud_client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, CLOUD_PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SmarterSpaConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, _platforms(entry))
