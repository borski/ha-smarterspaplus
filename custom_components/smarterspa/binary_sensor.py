"""Binary sensors. Local controller only."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SmarterSpaConfigEntry, local_entities


async def async_setup_entry(
    hass: HomeAssistant, entry: SmarterSpaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(
        local_entities.LocalBinarySensor(entry.runtime_data, d) for d in local_entities.BINARY_SENSORS
    )
