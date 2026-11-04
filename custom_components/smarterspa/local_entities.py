"""Entities for the local controller. Values come from its state snapshot.

Keys shared with cloud mode (power_level, salt_status, electrode_life,
zero_point, firmware, chlorine, lights, power_level_control,
zero_point_control) keep the same unique ids, so switching modes keeps them.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import math
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.button import ButtonDeviceClass, ButtonEntity, ButtonEntityDescription
from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfTime,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .entity import SmarterSpaEntity
from .local_coordinator import SmarterSpaLocalCoordinator

# The manual calls the sensor reading and the zero point millivolts.
MILLIVOLT = UnitOfElectricPotential.MILLIVOLT

SALT_OPTIONS = ["low", "ok", "high", "shutdown", "unknown"]
PHASE_OPTIONS = ["starting", "switching", "settling", "generating", "sampling", "idle", "fault"]
STOP_OPTIONS = ["completed", "target_reached", "manual", "overcurrent", "comm_lost"]

State = dict[str, Any]


def _minutes(key: str) -> Callable[[SmarterSpaLocalCoordinator], float | None]:
    def value(c: SmarterSpaLocalCoordinator) -> float | None:
        seconds = (c.data or {}).get(key)
        return None if seconds is None else round(seconds / 60, 1)

    return value


def _get(key: str) -> Callable[[SmarterSpaLocalCoordinator], Any]:
    return lambda c: (c.data or {}).get(key)


def _boot_time(c: SmarterSpaLocalCoordinator) -> datetime | None:
    uptime = (c.data or {}).get("uptime_s")
    if uptime is None:
        return None
    # Round to the minute so the timestamp doesn't jitter with each update.
    boot = dt_util.utcnow() - timedelta(seconds=uptime)
    return boot.replace(second=0, microsecond=0)


@dataclass(frozen=True, kw_only=True)
class LocalSensorDescription(SensorEntityDescription):
    value_fn: Callable[[SmarterSpaLocalCoordinator], Any]


SENSORS: tuple[LocalSensorDescription, ...] = (
    LocalSensorDescription(
        key="power_level", translation_key="power_level", icon="mdi:gauge",
        state_class=SensorStateClass.MEASUREMENT, value_fn=_get("power_level"),
    ),
    LocalSensorDescription(
        key="salt_status", translation_key="salt_status", icon="mdi:shaker-outline",
        device_class=SensorDeviceClass.ENUM, options=SALT_OPTIONS, value_fn=_get("salt_status"),
    ),
    LocalSensorDescription(
        key="electrode_life", translation_key="electrode_life", icon="mdi:battery-heart-variant",
        native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT,
        value_fn=_get("electrode_percent_remaining"),
    ),
    LocalSensorDescription(
        key="zero_point", translation_key="zero_point", icon="mdi:target",
        state_class=SensorStateClass.MEASUREMENT, entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_get("zero_point"),
    ),
    LocalSensorDescription(
        key="firmware", translation_key="firmware", icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC, value_fn=lambda c: c.firmware,
    ),
    LocalSensorDescription(
        key="last_boot", translation_key="last_boot", device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC, value_fn=_boot_time,
    ),
    LocalSensorDescription(
        key="electrode_current", translation_key="electrode_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=2,
        value_fn=_get("current_a"),
    ),
    LocalSensorDescription(
        key="chlorine_sensor", translation_key="chlorine_sensor", icon="mdi:flask-outline",
        native_unit_of_measurement=MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT, value_fn=_get("sensor"),
    ),
    LocalSensorDescription(
        key="last_check", translation_key="last_check", icon="mdi:flask-round-bottom-outline",
        native_unit_of_measurement=MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT, value_fn=_get("last_check"),
    ),
    LocalSensorDescription(
        key="target_point", translation_key="target_point", icon="mdi:arrow-collapse-up",
        native_unit_of_measurement=MILLIVOLT,
        entity_category=EntityCategory.DIAGNOSTIC, value_fn=_get("target_point"),
    ),
    LocalSensorDescription(
        key="cycle_phase", translation_key="cycle_phase", icon="mdi:state-machine",
        device_class=SensorDeviceClass.ENUM, options=PHASE_OPTIONS, value_fn=_get("phase"),
    ),
    LocalSensorDescription(
        key="cycle_remaining", translation_key="cycle_remaining",
        device_class=SensorDeviceClass.DURATION, native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0, value_fn=_minutes("cycle_remaining_s"),
    ),
    LocalSensorDescription(
        key="lockout_remaining", translation_key="lockout_remaining",
        device_class=SensorDeviceClass.DURATION, native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0, value_fn=_minutes("lockout_remaining_s"),
    ),
    LocalSensorDescription(
        key="electrode_hours", translation_key="electrode_hours",
        device_class=SensorDeviceClass.DURATION, native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING, suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC, value_fn=_get("electrode_hours"),
    ),
    LocalSensorDescription(
        key="last_stop", translation_key="last_stop", icon="mdi:stop-circle-outline",
        device_class=SensorDeviceClass.ENUM, options=STOP_OPTIONS,
        entity_category=EntityCategory.DIAGNOSTIC, value_fn=_get("last_stop"),
    ),
    LocalSensorDescription(
        key="comm_failures", translation_key="comm_failures", icon="mdi:lan-disconnect",
        state_class=SensorStateClass.TOTAL_INCREASING, entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_get("comm_failures_total"),
    ),
    LocalSensorDescription(
        key="wifi_signal", translation_key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT, entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.network.get("signal_dbm"),
    ),
)


class LocalSensor(SmarterSpaEntity, SensorEntity):
    entity_description: LocalSensorDescription
    coordinator: SmarterSpaLocalCoordinator

    def __init__(self, coordinator: SmarterSpaLocalCoordinator, description: LocalSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        value = self.entity_description.value_fn(self.coordinator)
        options = self.entity_description.options
        if self.entity_description.device_class == SensorDeviceClass.ENUM and value not in (options or []):
            return None
        return value


@dataclass(frozen=True, kw_only=True)
class LocalBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[SmarterSpaLocalCoordinator], bool | None]


BINARY_SENSORS: tuple[LocalBinaryDescription, ...] = (
    LocalBinaryDescription(
        key="generating", translation_key="generating", device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=_get("generating"),
    ),
    LocalBinaryDescription(
        key="fault", translation_key="fault", device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_get("fault"),
    ),
    LocalBinaryDescription(
        key="board_connected", translation_key="board_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY, entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_get("board_connected"),
    ),
    LocalBinaryDescription(
        key="internet", translation_key="internet", device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC, value_fn=lambda c: c.network.get("internet"),
    ),
)


class LocalBinarySensor(SmarterSpaEntity, BinarySensorEntity):
    entity_description: LocalBinaryDescription
    coordinator: SmarterSpaLocalCoordinator

    def __init__(self, coordinator: SmarterSpaLocalCoordinator, description: LocalBinaryDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator)


@dataclass(frozen=True, kw_only=True)
class LocalSwitchDescription(SwitchEntityDescription):
    value_fn: Callable[[SmarterSpaLocalCoordinator], bool | None]
    on: tuple[str, dict[str, Any]]
    off: tuple[str, dict[str, Any]]


SWITCHES: tuple[LocalSwitchDescription, ...] = (
    LocalSwitchDescription(
        # On for the whole cycle, including the few seconds before the cell energises.
        key="chlorine", translation_key="chlorine", icon="mdi:water-sync",
        value_fn=_get("in_cycle"), on=("start_cycle", {}), off=("stop_cycle", {}),
    ),
    LocalSwitchDescription(
        key="lights", translation_key="lights", icon="mdi:led-on", entity_category=EntityCategory.CONFIG,
        value_fn=_get("lights"),
        on=("update_settings", {"lights": True}), off=("update_settings", {"lights": False}),
    ),
    LocalSwitchDescription(
        key="auto", translation_key="auto", icon="mdi:refresh-auto", entity_category=EntityCategory.CONFIG,
        value_fn=_get("auto"),
        on=("update_settings", {"auto": True}), off=("update_settings", {"auto": False}),
    ),
    LocalSwitchDescription(
        # On: run until the sensor confirms recovery. Off: the original fixed run time.
        key="measured", translation_key="measured", icon="mdi:flask-outline",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda c: None if not c.data else c.data.get("mode") == "measured",
        on=("update_settings", {"mode": "measured"}), off=("update_settings", {"mode": "timed"}),
    ),
)


class LocalSwitch(SmarterSpaEntity, SwitchEntity):
    entity_description: LocalSwitchDescription
    coordinator: SmarterSpaLocalCoordinator

    def __init__(self, coordinator: SmarterSpaLocalCoordinator, description: LocalSwitchDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator)

    async def async_turn_on(self, **kwargs: Any) -> None:
        action, arguments = self.entity_description.on
        await self.coordinator.async_run(action, **arguments)

    async def async_turn_off(self, **kwargs: Any) -> None:
        action, arguments = self.entity_description.off
        await self.coordinator.async_run(action, **arguments)


@dataclass(frozen=True, kw_only=True)
class LocalNumberDescription(NumberEntityDescription):
    field: str


NUMBERS: tuple[LocalNumberDescription, ...] = (
    LocalNumberDescription(
        key="power_level", translation_key="power_level_control", icon="mdi:gauge",
        native_min_value=1, native_max_value=10, native_step=1, mode=NumberMode.SLIDER,
        field="power_level",
    ),
    LocalNumberDescription(
        key="zero_point", translation_key="zero_point_control", icon="mdi:target",
        native_min_value=10, native_max_value=150, native_step=1, mode=NumberMode.SLIDER,
        native_unit_of_measurement=MILLIVOLT,
        entity_category=EntityCategory.CONFIG, field="zero_point",
    ),
    LocalNumberDescription(
        key="target_margin", translation_key="target_margin", icon="mdi:arrow-expand-up",
        native_min_value=1, native_max_value=60, native_step=1, mode=NumberMode.BOX,
        native_unit_of_measurement=MILLIVOLT,
        entity_category=EntityCategory.CONFIG, field="target_margin",
    ),
)


class LocalNumber(SmarterSpaEntity, NumberEntity):
    entity_description: LocalNumberDescription
    coordinator: SmarterSpaLocalCoordinator

    def __init__(self, coordinator: SmarterSpaLocalCoordinator, description: LocalNumberDescription) -> None:
        super().__init__(coordinator, f"{description.key}_control")
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        value = (self.coordinator.data or {}).get(self.entity_description.field)
        return None if value is None else float(value)

    async def async_set_native_value(self, value: float) -> None:
        if not math.isfinite(value) or value != int(value):
            raise HomeAssistantError("SmarterSpa settings require a whole number")
        await self.coordinator.async_run("update_settings", **{self.entity_description.field: int(value)})


@dataclass(frozen=True, kw_only=True)
class LocalButtonDescription(ButtonEntityDescription):
    action: str


BUTTONS: tuple[LocalButtonDescription, ...] = (
    LocalButtonDescription(
        key="reset_electrode", translation_key="reset_electrode", icon="mdi:restore",
        entity_category=EntityCategory.CONFIG, action="reset_electrode",
    ),
    LocalButtonDescription(
        key="reboot", translation_key="reboot", device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG, action="reboot",
    ),
)


class LocalButton(SmarterSpaEntity, ButtonEntity):
    entity_description: LocalButtonDescription
    coordinator: SmarterSpaLocalCoordinator

    def __init__(self, coordinator: SmarterSpaLocalCoordinator, description: LocalButtonDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        await self.coordinator.async_run(self.entity_description.action)


POLARITY_OPTIONS = ["alternate", "normal", "reversed"]


class LocalPolaritySelect(SmarterSpaEntity, SelectEntity):
    """Cell polarity. Alternate sheds scale. Fixed is for a unit where one direction has failed."""

    coordinator: SmarterSpaLocalCoordinator
    entity_description = SelectEntityDescription(
        key="polarity",
        translation_key="polarity",
        icon="mdi:swap-horizontal",
        entity_category=EntityCategory.CONFIG,
        options=POLARITY_OPTIONS,
    )

    def __init__(self, coordinator: SmarterSpaLocalCoordinator) -> None:
        super().__init__(coordinator, "polarity")

    @property
    def current_option(self) -> str | None:
        value = (self.coordinator.data or {}).get("polarity")
        return value if value in POLARITY_OPTIONS else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_run("update_settings", polarity=option)
