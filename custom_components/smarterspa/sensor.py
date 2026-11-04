"""Sensors. All read from the Firestore document (reference 3.3)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SmarterSpaConfigEntry, is_local, local_entities
from .api import parse_boot_time
from .const import SALT_STATUS
from .coordinator import SmarterSpaCoordinator
from .entity import SmarterSpaEntity


@dataclass(frozen=True, kw_only=True)
class SmarterSpaSensorDescription(SensorEntityDescription):
    value_fn: Callable[[SmarterSpaCoordinator], Any]


def _salt_status(c: SmarterSpaCoordinator) -> str | None:
    code = c.main.get("s")
    if code is None:
        return None
    # 0 and 1 are verified. Anything else is surfaced as-is rather than guessed.
    return SALT_STATUS.get(int(code), f"unknown_{code}")


def _electrode_remaining(c: SmarterSpaCoordinator) -> int | None:
    used = c.main.get("e")
    if used is None:
        return None
    return max(0, min(100, 100 - int(used)))


def _last_boot(c: SmarterSpaCoordinator) -> datetime | None:
    return parse_boot_time(c.passport.get("t"))


SENSORS: tuple[SmarterSpaSensorDescription, ...] = (
    SmarterSpaSensorDescription(
        key="power_level",
        translation_key="power_level",
        icon="mdi:gauge",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.main.get("p"),
    ),
    SmarterSpaSensorDescription(
        key="salt_status",
        translation_key="salt_status",
        icon="mdi:shaker-outline",
        device_class=SensorDeviceClass.ENUM,
        options=[*SALT_STATUS.values()],
        value_fn=_salt_status,
    ),
    SmarterSpaSensorDescription(
        key="electrode_life",
        translation_key="electrode_life",
        icon="mdi:battery-heart-variant",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_electrode_remaining,
    ),
    SmarterSpaSensorDescription(
        key="zero_point",
        translation_key="zero_point",
        icon="mdi:target",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.settings.get("z"),
    ),
    SmarterSpaSensorDescription(
        key="firmware",
        translation_key="firmware",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.firmware,
    ),
    SmarterSpaSensorDescription(
        key="last_boot",
        translation_key="last_boot",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_last_boot,
    ),
    SmarterSpaSensorDescription(
        key="service_version",
        translation_key="service_version",
        icon="mdi:update",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.last_feed.get("v"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: SmarterSpaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if is_local(entry):
        async_add_entities(local_entities.LocalSensor(coordinator, d) for d in local_entities.SENSORS)
        return
    async_add_entities(SmarterSpaSensor(coordinator, d) for d in SENSORS)


class SmarterSpaSensor(SmarterSpaEntity, SensorEntity):
    entity_description: SmarterSpaSensorDescription

    def __init__(self, coordinator: SmarterSpaCoordinator, description: SmarterSpaSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        value = self.entity_description.value_fn(self.coordinator)
        # ENUM sensors must only report listed options. Unknown salt codes
        # go into an attribute instead of breaking the entity.
        if self.entity_description.device_class == SensorDeviceClass.ENUM and value not in (
            self.entity_description.options or []
        ):
            return None
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key == "salt_status":
            return {"raw_code": self.coordinator.main.get("s")}
        if self.entity_description.key == "electrode_life":
            return {"percent_used": self.coordinator.main.get("e")}
        return None
