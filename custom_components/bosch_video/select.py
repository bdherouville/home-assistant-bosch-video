"""Select platform for Bosch-specific camera modes."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BoschVideoConfigEntry, BoschVideoCoordinator
from .entity import BoschVideoEntity
from .models import BoschAudioEncoder


@dataclass(slots=True, frozen=True)
class BoschSelectDescription:
    """One capability-probed BICOM select."""

    key: str
    translation_key: str
    values: dict[str, int]


SELECTS = (
    BoschSelectDescription(
        "day_night_mode",
        "day_night_mode",
        {"automatic": 2, "color": 0, "monochrome": 1},
    ),
    BoschSelectDescription(
        "ir_illuminator",
        "ir_illuminator",
        {"off": 0, "on": 1, "automatic": 2},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoschVideoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up supported Bosch selects."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            *(
                BoschBicomSelect(coordinator, description)
                for description in SELECTS
                if description.key in coordinator.client.bicom_objects
            ),
            *(
                BoschAudioEncoderSelect(coordinator, encoder, setting, index)
                for index, encoder in enumerate(
                    coordinator.client.audio_encoders,
                    start=1,
                )
                for setting in ("encoding", "bitrate", "sample_rate")
            ),
        ]
    )


class BoschBicomSelect(BoschVideoEntity, SelectEntity):
    """A mapped Bosch BICOM enum."""

    def __init__(
        self,
        coordinator: BoschVideoCoordinator,
        description: BoschSelectDescription,
    ) -> None:
        """Initialize a select."""
        super().__init__(coordinator)
        self.description = description
        camera_id = coordinator.client.info.unique_id
        self._attr_unique_id = f"{camera_id}#bicom#{description.key}"
        self._attr_translation_key = description.translation_key
        self._attr_options = list(description.values)

    @property
    def current_option(self) -> str | None:
        """Return the option matching the camera value."""
        current = self.coordinator.data.rcp.get(self.description.key)
        return next(
            (
                option
                for option, value in self.description.values.items()
                if value == current
            ),
            None,
        )

    async def async_select_option(self, option: str) -> None:
        """Set and refresh the selected camera mode."""
        await self.coordinator.client.async_set_bicom(
            self.description.key,
            self.description.values[option],
        )
        await self.coordinator.async_request_refresh()


class BoschAudioEncoderSelect(BoschVideoEntity, SelectEntity):
    """A capability-constrained ONVIF audio encoder field."""

    def __init__(
        self,
        coordinator: BoschVideoCoordinator,
        encoder: BoschAudioEncoder,
        setting: str,
        index: int,
    ) -> None:
        """Initialize an audio encoder select."""
        super().__init__(coordinator)
        self.encoder = encoder
        self.setting = setting
        camera_id = coordinator.client.info.unique_id
        self._attr_unique_id = (
            f"{camera_id}#audio_encoder#{encoder.token}#{setting}"
        )
        self._attr_translation_key = f"audio_{setting}"
        self._attr_translation_placeholders = {"index": str(index)}

    @property
    def options(self) -> list[str]:
        """Return choices valid for the current codec."""
        if self.setting == "encoding":
            return list(self.encoder.options)
        current_encoding = self.coordinator.data.audio_encoders.get(
            self.encoder.token, {}
        ).get("encoding")
        codec_options = self.encoder.options.get(current_encoding)
        if codec_options is None:
            return []
        values = (
            codec_options.bitrates
            if self.setting == "bitrate"
            else codec_options.sample_rates
        )
        return [str(value) for value in values]

    @property
    def current_option(self) -> str | None:
        """Return the current encoder value."""
        state = self.coordinator.data.audio_encoders.get(self.encoder.token, {})
        value = state.get(self.setting)
        return str(value) if value not in (None, "") else None

    async def async_select_option(self, option: str) -> None:
        """Set and refresh one encoder field."""
        await self.coordinator.client.async_set_audio_encoder(
            self.encoder.token,
            self.setting,
            option,
        )
        await self.coordinator.async_request_refresh()
