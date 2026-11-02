"""Switches: chlorine generation (Main.g) and device lights (Settings.l)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SmarterSpaConfigEntry
from .const import CMD_CHLORINE_OFF, CMD_CHLORINE_ON, CMD_LIGHTS_OFF, CMD_LIGHTS_ON
from .coordinator import SmarterSpaCoordinator
from .entity import SmarterSpaEntity

SWITCHES: tuple[tuple[SwitchEntityDescription, str, str, str, str], ...] = (
    # description, section, field, on command, off command
    (
        SwitchEntityDescription(key="chlorine", translation_key="chlorine", icon="mdi:water-sync"),
        "Main",
        "g",
        CMD_CHLORINE_ON,
        CMD_CHLORINE_OFF,
    ),
    (
        SwitchEntityDescription(
            key="lights",
            translation_key="lights",
            icon="mdi:led-on",
            entity_category=EntityCategory.CONFIG,
        ),
        "Settings",
        "l",
        CMD_LIGHTS_ON,
        CMD_LIGHTS_OFF,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: SmarterSpaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(SmarterSpaSwitch(coordinator, *spec) for spec in SWITCHES)


class SmarterSpaSwitch(SmarterSpaEntity, SwitchEntity):
    def __init__(
        self,
        coordinator: SmarterSpaCoordinator,
        description: SwitchEntityDescription,
        section: str,
        field: str,
        on_cmd: str,
        off_cmd: str,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._section = section
        self._field = field
        self._on_cmd = on_cmd
        self._off_cmd = off_cmd
        self._assumed: bool | None = None

    @property
    def is_on(self) -> bool | None:
        section = (self.coordinator.data or {}).get(self._section) or {}
        value = section.get(self._field)
        if value is None:
            return None
        return int(value) == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_send_command(self._on_cmd)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_send_command(self._off_cmd)
