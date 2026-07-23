"""Number platform for Bosch Video imaging controls."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BoschVideoConfigEntry, BoschVideoCoordinator
from .entity import BoschVideoEntity
from .models import BoschImagingRange

TRANSLATION_KEYS = {
    "Brightness": "brightness",
    "ColorSaturation": "color_saturation",
    "Contrast": "contrast",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoschVideoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up supported imaging numbers."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            *(
                BoschImagingNumber(coordinator, setting)
                for setting in coordinator.client.imaging_ranges.values()
            ),
            *(
                [
                    BoschBicomNumber(
                        coordinator,
                        "ir_intensity",
                        "ir_intensity",
                    )
                ]
                if "ir_intensity" in coordinator.client.bicom_objects
                else []
            ),
        ]
    )


class BoschImagingNumber(BoschVideoEntity, NumberEntity):
    """Writable ONVIF imaging value."""

    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: BoschVideoCoordinator,
        setting: BoschImagingRange,
    ) -> None:
        """Initialize an imaging setting."""
        super().__init__(coordinator)
        self.setting = setting
        camera_id = coordinator.client.info.unique_id
        self._attr_unique_id = f"{camera_id}#imaging#{setting.key}"
        self._attr_translation_key = TRANSLATION_KEYS[setting.key]
        self._attr_native_min_value = setting.minimum
        self._attr_native_max_value = setting.maximum
        self._attr_native_step = setting.step

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.coordinator.data.imaging.get(self.setting.key)

    async def async_set_native_value(self, value: float) -> None:
        """Set and refresh the imaging value."""
        await self.coordinator.client.async_set_imaging(self.setting.key, value)
        await self.coordinator.async_request_refresh()


class BoschBicomNumber(BoschVideoEntity, NumberEntity):
    """Validated Bosch-specific numeric setting."""

    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: BoschVideoCoordinator,
        key: str,
        translation_key: str,
    ) -> None:
        """Initialize a BICOM setting."""
        super().__init__(coordinator)
        self.key = key
        obj = coordinator.client.bicom_objects[key]
        camera_id = coordinator.client.info.unique_id
        self._attr_unique_id = f"{camera_id}#bicom#{key}"
        self._attr_translation_key = translation_key
        self._attr_native_min_value = float(obj.minimum or 0)
        self._attr_native_max_value = float(obj.maximum or 100)
        self._attr_native_step = 1

    @property
    def native_value(self) -> float | None:
        """Return the current BICOM value."""
        value = self.coordinator.data.rcp.get(self.key)
        return float(value) if isinstance(value, int) else None

    async def async_set_native_value(self, value: float) -> None:
        """Set and refresh the BICOM value."""
        await self.coordinator.client.async_set_bicom(self.key, round(value))
        await self.coordinator.async_request_refresh()
