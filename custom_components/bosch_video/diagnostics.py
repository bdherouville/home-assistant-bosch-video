"""Diagnostics support for Bosch Video."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import BoschVideoConfigEntry

TO_REDACT = {
    "host",
    "password",
    "username",
    "serial_number",
    "mac_address",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: BoschVideoConfigEntry,
) -> dict[str, Any]:
    """Return privacy-preserving diagnostics."""
    return {
        "config_entry": async_redact_data(dict(entry.data), TO_REDACT),
        "camera": entry.runtime_data.client.diagnostics(),
    }
