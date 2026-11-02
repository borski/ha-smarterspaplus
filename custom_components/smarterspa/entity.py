"""Shared base entity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SmarterSpaCoordinator


class SmarterSpaEntity(CoordinatorEntity[SmarterSpaCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: SmarterSpaCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{coordinator.device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name="SmarterSpa+",
            manufacturer="ControlOMatic",
            model="SmarterSpa+",
            sw_version=coordinator.firmware,
        )
