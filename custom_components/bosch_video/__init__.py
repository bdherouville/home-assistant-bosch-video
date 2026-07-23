"""Bosch Video integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from onvif.exceptions import ONVIFError
from onvif.util import is_auth_error
from zeep.exceptions import Fault

from .client import BoschCameraClient
from .const import PLATFORMS
from .coordinator import BoschVideoConfigEntry, BoschVideoCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: BoschVideoConfigEntry) -> bool:
    """Set up Bosch Video from a config entry."""
    client = BoschCameraClient(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        async_get_clientsession(hass),
    )
    try:
        await client.async_initialize()
    except Fault as err:
        await client.async_close()
        if is_auth_error(err):
            raise ConfigEntryAuthFailed("Camera authentication failed") from err
        raise ConfigEntryNotReady(f"ONVIF error: {err}") from err
    except (TimeoutError, OSError, ONVIFError, ValueError) as err:
        await client.async_close()
        raise ConfigEntryNotReady(f"Unable to connect to the camera: {err}") from err

    coordinator = BoschVideoCoordinator(hass, entry, client)
    try:
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        await coordinator.events.async_start()
    except Exception:
        await coordinator.events.async_stop()
        await client.async_close()
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BoschVideoConfigEntry) -> bool:
    """Unload a Bosch Video config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.events.async_stop()
        await entry.runtime_data.client.async_close()
    return unloaded
