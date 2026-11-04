"""Fixtures. Local mode tests run the real smarterspa-local API on 127.0.0.1."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

from aiohttp.test_utils import TestServer
import pytest

from smarterspa.config import Config
from smarterspa.hardware.sim import SimulatedBoard, SimulatedPins
from smarterspa.http_api import build_app
from smarterspa.service import Service
from smarterspa.store import Store

TOKEN = "integration-test-token"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom_components/ in every test."""


@dataclass
class Controller:
    service: Service
    server: TestServer

    @property
    def host(self) -> str:
        return "127.0.0.1"

    @property
    def port(self) -> int:
        assert self.server.port is not None
        return self.server.port

    @property
    def entry_data(self) -> dict[str, object]:
        return {"connection": "local", "host": self.host, "port": self.port, "token": TOKEN}


async def _no_sleep(_: float) -> None:
    await asyncio.sleep(0)


@pytest.fixture
async def controller(tmp_path: Path, socket_enabled: None) -> AsyncIterator[Controller]:
    config = Config()
    config.api.token = TOKEN
    config.state.path = str(tmp_path / "state.json")
    config.state.vendor_prefs = str(tmp_path / "none")
    config.system.device_id = "testspa"
    config.network.enabled = False
    reboots: list[list[str]] = []
    service = Service(
        config,
        SimulatedBoard(sensor=60, decay_per_tick=0),
        SimulatedPins(),
        Store(Path(config.state.path)),
        tick_seconds=0,
        panel_sleep=_no_sleep,
        run_command=reboots.append,
    )
    service.reboots = reboots  # type: ignore[attr-defined]
    await service.tick()
    server = TestServer(build_app(service), host="127.0.0.1")
    await server.start_server()
    try:
        yield Controller(service, server)
    finally:
        await server.close()
