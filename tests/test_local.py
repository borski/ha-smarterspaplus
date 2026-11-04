"""Local mode against the real controller API."""

from __future__ import annotations

import asyncio

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.smarterspa.const import DOMAIN

from .conftest import TOKEN, Controller


async def _wait_for(hass: HomeAssistant, entity_id: str, expected: str, timeout: float = 5) -> None:
    async with asyncio.timeout(timeout):
        while (state := hass.states.get(entity_id)) is None or state.state != expected:
            await asyncio.sleep(0.05)
            await hass.async_block_till_done()


async def _setup(hass: HomeAssistant, controller: Controller, unique_id: str = "testspa") -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=unique_id, title="SmarterSpa+", data=controller.entry_data)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry


async def test_user_flow_local(hass: HomeAssistant, controller: Controller) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "local"})
    assert result["step_id"] == "local"

    bad = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": controller.host, "port": controller.port, "token": "wrong"}
    )
    assert bad["errors"] == {"base": "invalid_token"}

    unreachable = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": controller.host, "port": 1, "token": TOKEN}
    )
    assert unreachable["errors"] == {"base": "cannot_connect_local"}

    done = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": controller.host, "port": controller.port, "token": TOKEN}
    )
    assert done["type"] is FlowResultType.CREATE_ENTRY
    assert done["result"].unique_id == "testspa"
    assert done["data"]["connection"] == "local"
    await hass.async_block_till_done()


async def test_entities_and_values(hass: HomeAssistant, controller: Controller) -> None:
    await _setup(hass, controller)
    assert hass.states.get("sensor.smarterspa_power_level").state == "3"
    assert hass.states.get("sensor.smarterspa_salt_status").state == "unknown"
    assert hass.states.get("sensor.smarterspa_electrode_life_remaining").state == "100"
    # The test instance is metric. 102 °F from the board shows as 38.9 °C.
    assert round(float(hass.states.get("sensor.smarterspa_board_temperature").state), 1) == 38.9
    assert hass.states.get("sensor.smarterspa_cycle_phase").state == "idle"
    assert hass.states.get("binary_sensor.smarterspa_power_board").state == "on"
    assert hass.states.get("binary_sensor.smarterspa_generating").state == "off"
    assert hass.states.get("switch.smarterspa_chlorine_generation").state == "off"
    assert hass.states.get("switch.smarterspa_automatic_chlorination").state == "on"
    assert hass.states.get("number.smarterspa_power_level").state == "3.0"
    assert hass.states.get("button.smarterspa_reboot") is not None


async def test_commands_reach_the_controller(hass: HomeAssistant, controller: Controller) -> None:
    await _setup(hass, controller)
    engine = controller.service.engine

    await hass.services.async_call(
        "number", "set_value", {"entity_id": "number.smarterspa_power_level", "value": 6}, blocking=True
    )
    assert engine.settings.power_level == 6
    assert hass.states.get("number.smarterspa_power_level").state == "6.0"

    await hass.services.async_call(
        "number", "set_value", {"entity_id": "number.smarterspa_zero_point", "value": 14}, blocking=True
    )
    assert engine.settings.zero_point == 14

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.smarterspa_chlorine_generation"}, blocking=True
    )
    assert engine.in_cycle
    assert hass.states.get("switch.smarterspa_chlorine_generation").state == "on"

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.smarterspa_chlorine_generation"}, blocking=True
    )
    assert not engine.in_cycle

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.smarterspa_automatic_chlorination"}, blocking=True
    )
    assert engine.settings.auto is False

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.smarterspa_device_lights"}, blocking=True
    )
    assert engine.settings.lights is False

    engine.electrode_seconds = 10_000_000
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.smarterspa_reset_electrode_life"}, blocking=True
    )
    assert engine.electrode_seconds == 0


async def test_push_updates_without_polling(hass: HomeAssistant, controller: Controller) -> None:
    await _setup(hass, controller)
    await controller.service.set_power_level(9)
    await _wait_for(hass, "sensor.smarterspa_power_level", "9")
    controller.service.engine.start_cycle()
    for _ in range(14):
        await controller.service.tick()
    await _wait_for(hass, "binary_sensor.smarterspa_generating", "on")
    await _wait_for(hass, "sensor.smarterspa_cycle_phase", "generating")
    current = float(hass.states.get("sensor.smarterspa_electrode_current").state)
    assert 1.4 <= current <= 1.6


async def test_rejected_values_raise(hass: HomeAssistant, controller: Controller) -> None:
    await _setup(hass, controller)
    try:
        await hass.services.async_call(
            "number", "set_value", {"entity_id": "number.smarterspa_power_level", "value": 4.5}, blocking=True
        )
    except Exception as err:  # noqa: BLE001
        assert "whole number" in str(err)
    else:
        raise AssertionError("expected an error")
    assert controller.service.engine.settings.power_level == 3


async def test_reconfigure_cloud_to_local_keeps_unique_ids(hass: HomeAssistant, controller: Controller) -> None:
    cloud_id = "02:00:00:00:00:01"
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=cloud_id,
        title="SmarterSpa+",
        data={"email": "someone@example.com", "password": "x"},
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "sensor", DOMAIN, f"{cloud_id}_power_level", config_entry=entry,
        suggested_object_id="smarterspa_power_level",
    )

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "reconfigure_local"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": controller.host, "port": controller.port, "token": TOKEN}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    assert entry.data["connection"] == "local"
    assert "password" not in entry.data
    assert entry.unique_id == cloud_id
    assert entry.state is ConfigEntryState.LOADED
    # The pre-existing entity keeps its id and now reports local values.
    assert hass.states.get(old.entity_id).state == "3"
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{cloud_id}_electrode_current") is not None


async def test_reauth_local_token(hass: HomeAssistant, controller: Controller) -> None:
    entry = await _setup(hass, controller)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    bad = await hass.config_entries.flow.async_configure(result["flow_id"], {"token": "nope"})
    assert bad["errors"] == {"base": "invalid_token"}
    good = await hass.config_entries.flow.async_configure(result["flow_id"], {"token": TOKEN})
    assert good["reason"] == "reauth_successful"


async def test_unload(hass: HomeAssistant, controller: Controller) -> None:
    entry = await _setup(hass, controller)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
