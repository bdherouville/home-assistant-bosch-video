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

    def matches_unique_id(self, candidate: str | None) -> bool:
        """Match a config ID against either stable identifier."""
        if not candidate:
            return False
        normalized = candidate.casefold()
        return any(
            value and value.casefold() == normalized
            for value in (self.mac_address, self.serial_number)
        )


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


@dataclass(slots=True, frozen=True)
class BoschAudioEncoderOption:
    """Valid bitrate and sample-rate combinations for one codec."""

    encoding: str
    bitrates: tuple[int, ...]
    sample_rates: tuple[int, ...]


@dataclass(slots=True, frozen=True)
class BoschAudioEncoder:
    """One writable ONVIF audio encoder configuration."""

    token: str
    options: dict[str, BoschAudioEncoderOption]


@dataclass(slots=True, frozen=True)
class BoschAudioOutput:
    """One writable physical audio output."""

    configuration_token: str
    output_token: str
    minimum: int
    maximum: int


@dataclass(slots=True, frozen=True)
class BoschAnalyticsParameter:
    """One readable parameter from an active ONVIF analytics module."""

    key: str
    name: str


@dataclass(slots=True)
class BoschCameraState:
    """Mutable coordinator state."""

    imaging: dict[str, float] = field(default_factory=dict)
    rcp: dict[str, Any] = field(default_factory=dict)
    audio_encoders: dict[str, dict[str, str | int]] = field(default_factory=dict)
    audio_output_levels: dict[str, int] = field(default_factory=dict)
    analytics: dict[str, str] = field(default_factory=dict)
