from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .api import QBittorrentApi
from .const import (
    AUTH_API_KEY,
    AUTH_CREDENTIALS,
    CONF_API_KEY,
    CONF_AUTH_METHOD,
    CONF_CONNECTION_SPEED_MBPS,
    CONF_NAME,
    CONF_UPDATE_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
)
from .exceptions import QBittorrentError


class QBittorrentConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)
            if user_input[CONF_AUTH_METHOD] == AUTH_API_KEY:
                return await self.async_step_api_key()
            return await self.async_step_credentials()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default="qBittorrent"): vol.All(
                        str, vol.Length(min=1, max=100)
                    ),
                    vol.Required(CONF_HOST): str,
                    vol.Required(
                        CONF_AUTH_METHOD, default=AUTH_API_KEY
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": AUTH_API_KEY, "label": "API key"},
                                {
                                    "value": AUTH_CREDENTIALS,
                                    "label": "Username / password",
                                },
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL
                    ): bool,
                    vol.Optional(
                        CONF_UPDATE_INTERVAL,
                        default=DEFAULT_UPDATE_INTERVAL,
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(
                            min=MIN_UPDATE_INTERVAL,
                            max=MAX_UPDATE_INTERVAL,
                        ),
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_api_key(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_speed()

        return self.async_show_form(
            step_id="api_key",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
        )

    async def async_step_credentials(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_speed()

        return self.async_show_form(
            step_id="credentials",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
        )

    async def async_step_speed(self, user_input=None):
        """Optionally configure the internet connection speed."""
        if user_input is not None:
            self._data.update(user_input)
            return await self._async_validate_and_create()

        return self.async_show_form(
            step_id="speed",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_CONNECTION_SPEED_MBPS): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=10000,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                            unit_of_measurement="Mbps",
                        )
                    )
                }
            ),
        )

    async def _async_validate_and_create(self):
        host = self._data[CONF_HOST].rstrip("/")
        session = aiohttp.ClientSession(
            cookie_jar=aiohttp.CookieJar(unsafe=True)
        )

        kwargs = {}
        if self._data[CONF_AUTH_METHOD] == AUTH_API_KEY:
            kwargs["api_key"] = self._data[CONF_API_KEY]
        else:
            kwargs["username"] = self._data[CONF_USERNAME]
            kwargs["password"] = self._data[CONF_PASSWORD]

        api = QBittorrentApi(
            session,
            host,
            self._data[CONF_VERIFY_SSL],
            **kwargs,
        )

        try:
            info = await api.discover()
        except QBittorrentError:
            await session.close()
            return self.async_show_form(
                step_id=(
                    "api_key"
                    if self._data[CONF_AUTH_METHOD] == AUTH_API_KEY
                    else "credentials"
                ),
                data_schema=(
                    vol.Schema({vol.Required(CONF_API_KEY): str})
                    if self._data[CONF_AUTH_METHOD] == AUTH_API_KEY
                    else vol.Schema(
                        {
                            vol.Required(CONF_USERNAME): str,
                            vol.Required(CONF_PASSWORD): str,
                        }
                    )
                ),
                errors={"base": "cannot_connect"},
            )

        await session.close()

        await self.async_set_unique_id(host)
        self._abort_if_unique_id_configured()

        name = self._data.pop(CONF_NAME, "qBittorrent").strip() or "qBittorrent"
        connection_speed = self._data.pop(CONF_CONNECTION_SPEED_MBPS, None)
        options = {
            CONF_UPDATE_INTERVAL: self._data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
        }
        if connection_speed is not None:
            options[CONF_CONNECTION_SPEED_MBPS] = connection_speed
        return self.async_create_entry(title=name, data=self._data, options=options)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return QBittorrentOptionsFlowHandler()


class QBittorrentOptionsFlowHandler(config_entries.OptionsFlowWithReload):
    """Handle qBittorrent integration options."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            name = str(user_input.pop(CONF_NAME, self.config_entry.title)).strip()
            name = name or self.config_entry.title
            self.hass.config_entries.async_update_entry(
                self.config_entry, title=name
            )
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_NAME,
                            default=self.config_entry.title,
                        ): vol.All(
                            str, vol.Length(min=1, max=100)
                        ),
                        vol.Optional(
                            CONF_CONNECTION_SPEED_MBPS,
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=1,
                                max=10000,
                                step=1,
                                mode=selector.NumberSelectorMode.BOX,
                                unit_of_measurement="Mbps",
                            )
                        ),
                        vol.Required(
                            CONF_UPDATE_INTERVAL,
                            default=DEFAULT_UPDATE_INTERVAL,
                        ): vol.All(
                            vol.Coerce(int),
                            vol.Range(
                                min=MIN_UPDATE_INTERVAL,
                                max=MAX_UPDATE_INTERVAL,
                            ),
                        ),
                    }
                ),
                self.config_entry.options,
            ),
        )
