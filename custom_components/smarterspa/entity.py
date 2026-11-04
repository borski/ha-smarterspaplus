"""Shared base entity for both connection modes."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SmarterSpaCoordinator
from .local_coordinator import SmarterSpaLocalCoordinator

AnyCoordinator = SmarterSpaCoordinator | SmarterSpaLocalCoordinator


class SmarterSpaEntity(CoordinatorEntity[AnyCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: AnyCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        # Same unique ids in both modes, so switching keeps entity ids and history.
        self._attr_unique_id = f"{coordinator.device_id}_{key}"
        local = isinstance(coordinator, SmarterSpaLocalCoordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name="SmarterSpa+",
            manufacturer="ControlOMatic",
            model="SmarterSpa+ (local controller)" if local else "SmarterSpa+",
            sw_version=coordinator.firmware,
        )
