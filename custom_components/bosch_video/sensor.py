"""Sensor platform for Bosch Video."""

from __future__ import annotations

from hashlib import sha256

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
            *(
                [
                    BoschRecordingCountSensor(
                        coordinator,
                        SensorEntityDescription(
                            key="recordings",
                            translation_key="recordings",
                            entity_registry_enabled_default=False,
                        ),
                    ),
                    BoschRecordingCountSensor(
                        coordinator,
                        SensorEntityDescription(
                            key="recording_jobs",
                            translation_key="recording_jobs",
                            entity_registry_enabled_default=False,
                        ),
                    ),
                ]
                if coordinator.client.recording_supported
                else []
            ),
            *(
                BoschAnalyticsSensor(
                    coordinator,
                    parameter.key,
                    parameter.name,
                    index,
                )
                for index, parameter in enumerate(
                    coordinator.client.analytics_parameters,
                    start=1,
                )
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


class BoschAnalyticsSensor(BoschVideoEntity, SensorEntity):
    """A readable active ONVIF analytics module parameter."""

    def __init__(
        self,
        coordinator: BoschVideoCoordinator,
        key: str,
        name: str,
        index: int,
    ) -> None:
        """Initialize an analytics parameter sensor."""
        super().__init__(coordinator)
        self.key = key
        digest = sha256(key.encode()).hexdigest()[:16]
        camera_id = coordinator.client.info.unique_id
        self._attr_unique_id = f"{camera_id}#analytics#{digest}"
        self._attr_translation_key = (
            "analytics_mode" if name == "Mode" else "analytics_type"
        )
        self._attr_translation_placeholders = {"index": str(index)}

    @property
    def native_value(self) -> str | None:
        """Return the current analytics module value."""
        return self.coordinator.data.analytics.get(self.key)


class BoschRecordingCountSensor(BoschVideoEntity, SensorEntity):
    """A live diagnostic count from the ONVIF Recording service."""

    def __init__(
        self,
        coordinator: BoschVideoCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize one recording inventory count."""
        super().__init__(coordinator)
        self.entity_description = description
        camera_id = coordinator.client.info.unique_id
        self._attr_unique_id = f"{camera_id}#{description.key}"

    @property
    def native_value(self) -> int:
        """Return the current recording or job count."""
        if self.entity_description.key == "recordings":
            return self.coordinator.client.recording_count
        return self.coordinator.client.recording_job_count
