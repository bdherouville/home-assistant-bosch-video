"""Sensor platform for Bosch Video."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BoschVideoConfigEntry, BoschVideoCoordinator
from .entity import BoschVideoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoschVideoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up diagnostic sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            BoschCountSensor(
                coordinator,
                SensorEntityDescription(
                    key="media_profiles",
                    translation_key="media_profiles",
                    entity_registry_enabled_default=False,
                ),
                len(coordinator.client.profiles),
            ),
            BoschCountSensor(
                coordinator,
                SensorEntityDescription(
                    key="onvif_services",
                    translation_key="onvif_services",
                    entity_registry_enabled_default=False,
                ),
                len(coordinator.client.service_namespaces),
            ),
        ]
    )


class BoschCountSensor(BoschVideoEntity, SensorEntity):
    """Static diagnostic count."""

    _attr_native_unit_of_measurement = None

    def __init__(
        self,
        coordinator: BoschVideoCoordinator,
        description: SensorEntityDescription,
        value: int,
    ) -> None:
        """Initialize the count sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_native_value = value
        camera_id = coordinator.client.info.unique_id
        self._attr_unique_id = f"{camera_id}#{description.key}"
