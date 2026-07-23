"""Data coordinator for Bosch Video."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import BoschCameraClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER
from .models import BoschCameraState

type BoschVideoConfigEntry = ConfigEntry[BoschVideoCoordinator]


class BoschVideoCoordinator(DataUpdateCoordinator[BoschCameraState]):
    """Coordinate camera state shared by entity platforms."""

    config_entry: BoschVideoConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: BoschVideoConfigEntry,
        client: BoschCameraClient,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}_{config_entry.entry_id}",
            update_interval=DEFAULT_SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self.client = client

    async def _async_update_data(self) -> BoschCameraState:
        """Fetch current camera state."""
        try:
            return await self.client.async_update()
        except Exception as err:
            raise UpdateFailed(f"Unable to update the Bosch camera: {err}") from err
