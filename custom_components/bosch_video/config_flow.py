"""Config flow for Bosch Video."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from onvif.exceptions import ONVIFError
from onvif.util import is_auth_error
from zeep.exceptions import Fault, TransportError

from .client import BoschCameraClient
from .const import DEFAULT_PORT, DOMAIN


class BoschVideoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Bosch Video config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure a camera manually."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = BoschCameraClient(
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                async_get_clientsession(self.hass),
            )
            try:
                await client.async_initialize()
                if client.info is None:
                    raise ValueError("Missing device information")
                existing = next(
                    (
                        entry
                        for entry in self._async_current_entries()
                        if client.info.matches_unique_id(entry.unique_id)
                    ),
                    None,
                )
                await self.async_set_unique_id(
                    existing.unique_id if existing else client.info.unique_id
                )
                self._abort_if_unique_id_configured(
                    updates={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                    }
                )
                title = f"{client.info.manufacturer} {client.info.model}"
            except Fault as err:
                errors["base"] = "invalid_auth" if is_auth_error(err) else "onvif_error"
            except TransportError as err:
                errors["base"] = (
                    "invalid_auth"
                    if err.status_code in (401, 403)
                    else "cannot_connect"
                )
            except (TimeoutError, OSError, ONVIFError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=title, data=user_input)
            finally:
                await client.async_close()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOST,
                    default=(user_input or {}).get(CONF_HOST, ""),
                ): str,
                vol.Required(
                    CONF_PORT,
                    default=(user_input or {}).get(CONF_PORT, DEFAULT_PORT),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Required(
                    CONF_USERNAME,
                    default=(user_input or {}).get(CONF_USERNAME, "service"),
                ): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Start reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update credentials for an existing entry."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = dict(entry.data)
            data.update(user_input)
            client = BoschCameraClient(
                data[CONF_HOST],
                data[CONF_PORT],
                data[CONF_USERNAME],
                data[CONF_PASSWORD],
                async_get_clientsession(self.hass),
            )
            try:
                await client.async_initialize()
                if (
                    client.info is None
                    or not client.info.matches_unique_id(entry.unique_id)
                ):
                    errors["base"] = "wrong_camera"
                    return self.async_show_form(
                        step_id="reauth_confirm",
                        data_schema=self._reauth_schema(entry, user_input),
                        errors=errors,
                    )
            except (Fault, TransportError, ONVIFError, TimeoutError, OSError):
                errors["base"] = "invalid_auth"
            else:
                return self.async_update_reload_and_abort(entry, data=data)
            finally:
                await client.async_close()

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self._reauth_schema(entry, user_input),
            errors=errors,
        )

    def _reauth_schema(
        self,
        entry: Any,
        user_input: dict[str, Any] | None,
    ) -> vol.Schema:
        """Return the credential form without ever pre-filling a password."""
        return vol.Schema(
            {
                vol.Required(
                    CONF_USERNAME,
                    default=(user_input or entry.data).get(CONF_USERNAME, "service"),
                ): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Update the Home Assistant connection address for the same camera."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = dict(entry.data)
            data.update(user_input)
            client = BoschCameraClient(
                data[CONF_HOST],
                data[CONF_PORT],
                data[CONF_USERNAME],
                data[CONF_PASSWORD],
                async_get_clientsession(self.hass),
            )
            try:
                await client.async_initialize()
                if (
                    client.info is None
                    or not client.info.matches_unique_id(entry.unique_id)
                ):
                    errors["base"] = "wrong_camera"
                else:
                    return self.async_update_reload_and_abort(entry, data=data)
            except Fault as err:
                errors["base"] = (
                    "invalid_auth" if is_auth_error(err) else "onvif_error"
                )
            except TransportError as err:
                errors["base"] = (
                    "invalid_auth"
                    if err.status_code in (401, 403)
                    else "cannot_connect"
                )
            except (TimeoutError, OSError, ONVIFError, ValueError):
                errors["base"] = "cannot_connect"
            finally:
                await client.async_close()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=(user_input or entry.data).get(CONF_HOST, ""),
                    ): str,
                    vol.Required(
                        CONF_PORT,
                        default=(user_input or entry.data).get(
                            CONF_PORT,
                            DEFAULT_PORT,
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                }
            ),
            errors=errors,
        )
