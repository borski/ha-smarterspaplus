"""Number entities: power level (1..10) and zero point (10..150)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import math

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SmarterSpaConfigEntry, is_local, local_entities
from .const import cmd_power_level, cmd_zero_point
from .coordinator import SmarterSpaCoordinator
from .entity import SmarterSpaEntity


@dataclass(frozen=True, kw_only=True)
class SmarterSpaNumberDescription(NumberEntityDescription):
    section: str
    field: str
    command_fn: Callable[[int], str]


NUMBERS: tuple[SmarterSpaNumberDescription, ...] = (
    SmarterSpaNumberDescription(
        key="power_level",
        translation_key="power_level_control",
        icon="mdi:gauge",
        native_min_value=1,
        native_max_value=10,
        native_step=1,
        mode=NumberMode.SLIDER,
        section="Main",
        field="p",
        command_fn=cmd_power_level,
    ),
    SmarterSpaNumberDescription(
        key="zero_point",
        translation_key="zero_point_control",
        icon="mdi:target",
        native_min_value=10,
        native_max_value=150,
        native_step=1,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
        section="Settings",
        field="z",
        command_fn=cmd_zero_point,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: SmarterSpaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if is_local(entry):
        async_add_entities(local_entities.LocalNumber(coordinator, d) for d in local_entities.NUMBERS)
        return
    async_add_entities(SmarterSpaNumber(coordinator, d) for d in NUMBERS)


class SmarterSpaNumber(SmarterSpaEntity, NumberEntity):
    entity_description: SmarterSpaNumberDescription

    def __init__(self, coordinator: SmarterSpaCoordinator, description: SmarterSpaNumberDescription) -> None:
        # Distinct unique_id from the read-only sensor of the same name.
        super().__init__(coordinator, f"{description.key}_control")
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        section = (self.coordinator.data or {}).get(self.entity_description.section) or {}
        value = section.get(self.entity_description.field)
        return None if value is None else float(value)

    async def async_set_native_value(self, value: float) -> None:
        if not math.isfinite(value) or value != int(value):
            raise HomeAssistantError("SmarterSpa settings require a whole number")
        await self.coordinator.async_send_command(self.entity_description.command_fn(int(value)))
