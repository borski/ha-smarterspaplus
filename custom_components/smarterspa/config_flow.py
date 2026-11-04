"""Config flow. Cloud account, or the local controller's address and API token.

Reconfigure switches an existing entry between cloud and local in place, so
entity IDs and history carry over.
"""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SmarterSpaApiError, SmarterSpaAuthError, SmarterSpaClient
from .const import (
    CONF_CONNECTION,
    CONF_TOKEN,
    CONNECTION_CLOUD,
    CONNECTION_LOCAL,
    DEFAULT_LOCAL_PORT,
    DOMAIN,
)
from .local_api import LocalApiError, LocalAuthError, LocalClient

CLOUD_SCHEMA = vol.Schema({vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str})


def _local_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_LOCAL_PORT)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
            vol.Required(CONF_TOKEN): str,
        }
    )


class SmarterSpaConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    # Validation

    async def _check_cloud(self, user_input: dict[str, Any]) -> tuple[str | None, str | None]:
        """Returns (device id, error key)."""
        client = SmarterSpaClient(
            async_get_clientsession(self.hass), user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
        )
        try:
            uid = await client.sign_in()
            doc = await client.get_document()
        except SmarterSpaAuthError:
            return None, "invalid_auth"
        except (SmarterSpaApiError, aiohttp.ClientError, TimeoutError):
            return None, "cannot_connect"
        return str((doc.get("Pass") or {}).get("m") or uid), None

    async def _check_local(self, user_input: dict[str, Any]) -> tuple[str | None, str | None]:
        client = LocalClient(
            async_get_clientsession(self.hass),
            user_input[CONF_HOST],
            user_input[CONF_PORT],
            user_input[CONF_TOKEN],
        )
        try:
            state = await client.get_state()
        except LocalAuthError:
            return None, "invalid_token"
        except LocalApiError:
            return None, "cannot_connect_local"
        device_id = state.get("device_id")
        if not isinstance(device_id, str) or not device_id:
            return None, "not_a_controller"
        return device_id, None

    # New entries

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=[CONNECTION_LOCAL, CONNECTION_CLOUD])

    async def async_step_cloud(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            device_id, error = await self._check_cloud(user_input)
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="SmarterSpa+", data={CONF_CONNECTION: CONNECTION_CLOUD, **user_input}
                )
        return self.async_show_form(step_id="cloud", data_schema=CLOUD_SCHEMA, errors=errors)

    async def async_step_local(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            device_id, error = await self._check_local(user_input)
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured(updates=user_input)
                return self.async_create_entry(
                    title="SmarterSpa+", data={CONF_CONNECTION: CONNECTION_LOCAL, **user_input}
                )
        return self.async_show_form(
            step_id="local", data_schema=_local_schema(user_input), errors=errors
        )

    # Reconfigure: switch modes or change details, keeping the entry and its entities

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="reconfigure", menu_options=["reconfigure_local", "reconfigure_cloud"]
        )

    async def async_step_reconfigure_local(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            _, error = await self._check_local(user_input)
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry, data={CONF_CONNECTION: CONNECTION_LOCAL, **user_input}
                )
        defaults = user_input or (entry.data if entry.data.get(CONF_CONNECTION) == CONNECTION_LOCAL else {})
        return self.async_show_form(
            step_id="reconfigure_local", data_schema=_local_schema(defaults), errors=errors
        )

    async def async_step_reconfigure_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            _, error = await self._check_cloud(user_input)
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry, data={CONF_CONNECTION: CONNECTION_CLOUD, **user_input}
                )
        return self.async_show_form(step_id="reconfigure_cloud", data_schema=CLOUD_SCHEMA, errors=errors)

    # Reauth: password for cloud, token for local

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        local = entry.data.get(CONF_CONNECTION) == CONNECTION_LOCAL
        field = CONF_TOKEN if local else CONF_PASSWORD
        errors: dict[str, str] = {}
        if user_input is not None:
            candidate = {**entry.data, field: user_input[field]}
            _, error = await (self._check_local(candidate) if local else self._check_cloud(candidate))
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(entry, data_updates={field: user_input[field]})
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(field): str}),
            description_placeholders={"what": "API token" if local else "password"},
            errors=errors,
        )
