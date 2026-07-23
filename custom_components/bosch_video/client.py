"""Async Bosch camera client built on ONVIF."""

from __future__ import annotations

import os
from contextlib import suppress
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import onvif
from aiohttp import ClientSession
from onvif import ONVIFCamera

from .bicom import KNOWN_OBJECTS, BicomError, BicomObject, BoschBicomClient
from .models import (
    BoschCameraState,
    BoschDeviceInfo,
    BoschImagingRange,
    BoschMediaProfile,
    BoschRelay,
)
from .rcp import BoschRcpClient


def _value(obj: Any, name: str, default: Any = None) -> Any:
    """Read a Zeep object or mapping without relying on one representation."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class BoschCameraClient:
    """Manage one Bosch camera and its ONVIF services."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        session: ClientSession,
    ) -> None:
        """Initialize the client without performing I/O."""
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.rcp = BoschRcpClient(session, host, username, password, port=port)
        self.bicom = BoschBicomClient(self.rcp)
        self.device = ONVIFCamera(
            host,
            port,
            username,
            password,
            f"{os.path.dirname(onvif.__file__)}/wsdl/",
            no_cache=True,
            adjust_time=True,
        )
        self.info: BoschDeviceInfo | None = None
        self.profiles: list[BoschMediaProfile] = []
        self.imaging_ranges: dict[str, BoschImagingRange] = {}
        self.relays: list[BoschRelay] = []
        self.service_namespaces: set[str] = set()
        self.bicom_objects: dict[str, BicomObject] = {}
        self.bicom_values: dict[str, int | bytes] = {}

    async def async_initialize(self) -> None:
        """Connect, authenticate and inventory supported capabilities."""
        await self.device.update_xaddrs()
        self.service_namespaces = set(self.device.xaddrs)

        device_mgmt = await self.device.create_devicemgmt_service()
        raw_info = await device_mgmt.GetDeviceInformation()

        mac_address: str | None = None
        with suppress(Exception):
            interfaces = await device_mgmt.GetNetworkInterfaces()
            for interface in interfaces or []:
                if not _value(interface, "Enabled", False):
                    continue
                candidate = _value(_value(interface, "Info"), "HwAddress")
                if candidate:
                    mac_address = str(candidate).upper()
                    break

        self.info = BoschDeviceInfo(
            manufacturer=str(_value(raw_info, "Manufacturer", "Bosch")),
            model=str(_value(raw_info, "Model", "Bosch IP camera")),
            firmware_version=str(_value(raw_info, "FirmwareVersion", "")),
            serial_number=str(_value(raw_info, "SerialNumber", "")),
            mac_address=mac_address,
        )
        if not self.info.unique_id:
            raise ValueError("The camera did not expose a stable identifier")

        await self._async_load_profiles()
        await self._async_load_imaging()
        await self._async_load_relays()
        await self._async_load_bicom()

    async def _async_load_profiles(self) -> None:
        """Load H.264 ONVIF media profiles."""
        media = await self.device.create_media_service()
        raw_profiles = await media.GetProfiles()
        profiles: list[BoschMediaProfile] = []
        for raw_profile in raw_profiles or []:
            encoder = _value(raw_profile, "VideoEncoderConfiguration")
            if encoder is None:
                continue
            encoding = str(_value(encoder, "Encoding", ""))
            if encoding.upper() != "H264":
                continue
            resolution = _value(encoder, "Resolution")
            source_config = _value(raw_profile, "VideoSourceConfiguration")
            profiles.append(
                BoschMediaProfile(
                    token=str(_value(raw_profile, "token", "")),
                    name=str(_value(raw_profile, "Name", "H.264")),
                    encoding=encoding,
                    width=int(_value(resolution, "Width", 0)),
                    height=int(_value(resolution, "Height", 0)),
                    video_source_token=(
                        str(_value(source_config, "SourceToken"))
                        if _value(source_config, "SourceToken")
                        else None
                    ),
                )
            )
        if not profiles:
            raise ValueError("The camera does not expose an H.264 ONVIF profile")
        self.profiles = profiles

    async def _async_load_imaging(self) -> None:
        """Discover writable imaging fields and ranges."""
        source_token = self.primary_profile.video_source_token
        if not source_token:
            return
        with suppress(Exception):
            imaging = await self.device.create_imaging_service()
            options = await imaging.GetOptions({"VideoSourceToken": source_token})
            ranges: dict[str, BoschImagingRange] = {}
            for key in ("Brightness", "ColorSaturation", "Contrast"):
                option = _value(options, key)
                if option is None:
                    continue
                minimum = float(_value(option, "Min", 0))
                maximum = float(_value(option, "Max", 255))
                ranges[key] = BoschImagingRange(key, minimum, maximum)
            self.imaging_ranges = ranges

    async def _async_load_relays(self) -> None:
        """Discover relay outputs if DeviceIO is supported."""
        with suppress(Exception):
            deviceio = await self.device.create_deviceio_service()
            raw_relays = await deviceio.GetRelayOutputs()
            relays: list[BoschRelay] = []
            for raw_relay in raw_relays or []:
                properties = _value(raw_relay, "Properties")
                relays.append(
                    BoschRelay(
                        token=str(_value(raw_relay, "token", "")),
                        mode=(
                            str(_value(properties, "Mode"))
                            if _value(properties, "Mode")
                            else None
                        ),
                        idle_state=(
                            str(_value(properties, "IdleState"))
                            if _value(properties, "IdleState")
                            else None
                        ),
                    )
                )
            self.relays = relays

    async def _async_load_bicom(self) -> None:
        """Probe the small, model-specific BICOM capability allowlist."""
        for key in ("day_night_mode", "ir_illuminator", "ir_intensity"):
            obj = KNOWN_OBJECTS[key]
            try:
                response = await self.bicom.async_get(obj)
            except (BicomError, OSError, TimeoutError):
                continue
            self.bicom_objects[key] = obj
            self.bicom_values[key] = response.value

    @property
    def primary_profile(self) -> BoschMediaProfile:
        """Return the first H.264 profile."""
        return self.profiles[0]

    async def async_update(self) -> BoschCameraState:
        """Fetch lightweight mutable state."""
        state = BoschCameraState()
        source_token = self.primary_profile.video_source_token
        if source_token and self.imaging_ranges:
            imaging = await self.device.create_imaging_service()
            settings = await imaging.GetImagingSettings(
                {"VideoSourceToken": source_token}
            )
            for key in self.imaging_ranges:
                current = _value(settings, key)
                if current is not None:
                    state.imaging[key] = float(current)
        for key, obj in self.bicom_objects.items():
            try:
                self.bicom_values[key] = (await self.bicom.async_get(obj)).value
            except (BicomError, OSError, TimeoutError):
                continue
        state.rcp = dict(self.bicom_values)
        return state

    async def async_set_imaging(self, key: str, value: float) -> None:
        """Persist one validated ONVIF imaging setting."""
        setting_range = self.imaging_ranges[key]
        if not setting_range.minimum <= value <= setting_range.maximum:
            raise ValueError(f"{key} is outside the supported range")
        source_token = self.primary_profile.video_source_token
        if not source_token:
            raise RuntimeError("No ONVIF video source is available")
        imaging = await self.device.create_imaging_service()
        await imaging.SetImagingSettings(
            {
                "VideoSourceToken": source_token,
                "ImagingSettings": {key: value},
                "ForcePersistence": True,
            }
        )

    async def async_set_relay(self, token: str, active: bool) -> None:
        """Set one ONVIF relay output."""
        if token not in {relay.token for relay in self.relays}:
            raise ValueError("Unknown relay token")
        deviceio = await self.device.create_deviceio_service()
        await deviceio.SetRelayOutputState(
            {
                "RelayOutputToken": token,
                "LogicalState": "active" if active else "inactive",
            }
        )

    async def async_set_bicom(self, key: str, value: int) -> None:
        """Set one capability-probed BICOM object."""
        obj = self.bicom_objects[key]
        await self.bicom.async_set(obj, value)
        self.bicom_values[key] = value

    async def async_get_stream_uri(self, profile: BoschMediaProfile) -> str:
        """Return a credentialed RTSP source for Home Assistant stream."""
        media = await self.device.create_media_service()
        response = await media.GetStreamUri(
            {
                "ProfileToken": profile.token,
                "StreamSetup": {
                    "Stream": "RTP-Unicast",
                    "Transport": {"Protocol": "RTSP"},
                },
            }
        )
        return self._credentialed_uri(str(_value(response, "Uri", "")))

    async def async_get_snapshot(self, profile: BoschMediaProfile) -> bytes:
        """Fetch a JPEG snapshot with ONVIF-managed Digest authentication."""
        result = await self.device.get_snapshot(profile.token, basic_auth=False)
        if not isinstance(result, bytes):
            raise RuntimeError("The camera returned an invalid snapshot")
        return result

    def _credentialed_uri(self, uri: str) -> str:
        """Insert credentials into a URI without logging or persisting it."""
        parsed = urlsplit(uri)
        hostname = parsed.hostname or self.host
        port = f":{parsed.port}" if parsed.port else ""
        userinfo = f"{quote(self.username, safe='')}:{quote(self.password, safe='')}@"
        return urlunsplit(
            (
                parsed.scheme,
                f"{userinfo}{hostname}{port}",
                parsed.path,
                parsed.query,
                "",
            )
        )

    def diagnostics(self) -> dict[str, Any]:
        """Return data safe for Home Assistant diagnostics redaction."""
        return {
            "device": {
                "manufacturer": self.info.manufacturer if self.info else None,
                "model": self.info.model if self.info else None,
                "firmware_version": (self.info.firmware_version if self.info else None),
            },
            "profiles": [
                {
                    "name": profile.name,
                    "encoding": profile.encoding,
                    "width": profile.width,
                    "height": profile.height,
                }
                for profile in self.profiles
            ],
            "imaging_ranges": {
                key: {
                    "minimum": value.minimum,
                    "maximum": value.maximum,
                    "step": value.step,
                }
                for key, value in self.imaging_ranges.items()
            },
            "relay_count": len(self.relays),
            "bicom_capabilities": sorted(self.bicom_objects),
            "service_namespaces": sorted(self.service_namespaces),
        }

    async def async_close(self) -> None:
        """Close ONVIF transports."""
        await self.device.close()
