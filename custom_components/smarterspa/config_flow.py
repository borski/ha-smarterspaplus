"""Config flow: account email and password only."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SmarterSpaApiError, SmarterSpaAuthError, SmarterSpaClient
from .const import DOMAIN

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class SmarterSpaConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            client = SmarterSpaClient(
                async_get_clientsession(self.hass), user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            try:
                uid = await client.sign_in()
                doc = await client.get_document()
            except SmarterSpaAuthError:
                errors["base"] = "invalid_auth"
            except SmarterSpaApiError:
                errors["base"] = "cannot_connect"
            else:
                device_id = str((doc.get("Pass") or {}).get("m") or uid)
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="SmarterSpa+", data=user_input)

        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            client = SmarterSpaClient(
                async_get_clientsession(self.hass), entry.data[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            try:
                await client.sign_in()
            except SmarterSpaAuthError:
                errors["base"] = "invalid_auth"
            except SmarterSpaApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )
