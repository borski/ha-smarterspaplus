"""Button: ask the device to check for updates. Reply shows up in Feed."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SmarterSpaConfigEntry
from .const import CMD_UPDATE_CHECK
from .coordinator import SmarterSpaCoordinator
from .entity import SmarterSpaEntity

DESCRIPTION = ButtonEntityDescription(
    key="check_updates",
    translation_key="check_updates",
    icon="mdi:update",
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: SmarterSpaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([SmarterSpaUpdateCheckButton(entry.runtime_data)])


class SmarterSpaUpdateCheckButton(SmarterSpaEntity, ButtonEntity):
    entity_description = DESCRIPTION

    def __init__(self, coordinator: SmarterSpaCoordinator) -> None:
        super().__init__(coordinator, DESCRIPTION.key)

    async def async_press(self) -> None:
        await self.coordinator.async_send_command(CMD_UPDATE_CHECK)
