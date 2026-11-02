"""SmarterSpa+ (ControlOMatic) via its Firebase cloud backend."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SmarterSpaApiError, SmarterSpaAuthError, SmarterSpaClient
from .coordinator import SmarterSpaCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH, Platform.NUMBER, Platform.BUTTON]

SmarterSpaConfigEntry = ConfigEntry[SmarterSpaCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SmarterSpaConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    client = SmarterSpaClient(session, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
    try:
        await client.sign_in()
    except SmarterSpaAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except SmarterSpaApiError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = SmarterSpaCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SmarterSpaConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
