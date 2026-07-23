"""Runtime data models for Bosch Video."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class BoschDeviceInfo:
    """Stable camera identity."""

    manufacturer: str
    model: str
    firmware_version: str
    serial_number: str
    mac_address: str | None = None

    @property
    def unique_id(self) -> str:
        """Return the best available stable identifier."""
        return self.mac_address or self.serial_number


@dataclass(slots=True, frozen=True)
class BoschMediaProfile:
    """ONVIF media profile used by Home Assistant."""

    token: str
    name: str
    encoding: str
    width: int
    height: int
    video_source_token: str | None


@dataclass(slots=True, frozen=True)
class BoschImagingRange:
    """One writable imaging setting and its valid range."""

    key: str
    minimum: float
    maximum: float
    step: float = 1.0


@dataclass(slots=True, frozen=True)
class BoschRelay:
    """ONVIF relay output."""

    token: str
    mode: str | None
    idle_state: str | None


@dataclass(slots=True)
class BoschCameraState:
    """Mutable coordinator state."""

    imaging: dict[str, float] = field(default_factory=dict)
    rcp: dict[str, Any] = field(default_factory=dict)
