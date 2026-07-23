"""Shared Bosch Video entity helpers."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BoschVideoCoordinator


class BoschVideoEntity(CoordinatorEntity[BoschVideoCoordinator]):
    """Base class for entities belonging to one Bosch camera."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BoschVideoCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        camera_info = coordinator.client.info
        if camera_info is None:
            raise RuntimeError("Camera information is unavailable")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, camera_info.unique_id)},
            manufacturer=camera_info.manufacturer,
            model=camera_info.model,
            serial_number=camera_info.serial_number,
            sw_version=camera_info.firmware_version,
            name=f"{camera_info.manufacturer} {camera_info.model}",
        )
