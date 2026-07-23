"""Camera platform for Bosch Video."""

from __future__ import annotations

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BoschVideoConfigEntry, BoschVideoCoordinator
from .entity import BoschVideoEntity
from .models import BoschMediaProfile


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoschVideoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one entity per H.264 profile."""
    coordinator = entry.runtime_data
    async_add_entities(
        BoschProfileCamera(coordinator, profile)
        for profile in coordinator.client.profiles
    )


class BoschProfileCamera(BoschVideoEntity, Camera):
    """A Bosch ONVIF media profile."""

    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_content_type = "image/jpeg"

    def __init__(
        self,
        coordinator: BoschVideoCoordinator,
        profile: BoschMediaProfile,
    ) -> None:
        """Initialize a profile camera."""
        Camera.__init__(self)
        BoschVideoEntity.__init__(self, coordinator)
        self.profile = profile
        camera_id = coordinator.client.info.unique_id
        self._attr_unique_id = f"{camera_id}#profile#{profile.token}"
        self._attr_name = f"{profile.name} {profile.width}×{profile.height}"

    async def stream_source(self) -> str | None:
        """Return a credentialed RTSP stream URI."""
        return await self.coordinator.client.async_get_stream_uri(self.profile)

    async def async_camera_image(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes | None:
        """Return a JPEG snapshot."""
        return await self.coordinator.client.async_get_snapshot(self.profile)
