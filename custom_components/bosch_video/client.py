"""Async Bosch camera client built on ONVIF."""

from __future__ import annotations

import os
from contextlib import suppress
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import onvif
from aiohttp import ClientSession
from onvif import ONVIFCamera

from .audio import validated_audio_values
from .bicom import KNOWN_OBJECTS, BicomError, BicomObject, BoschBicomClient
from .models import (
    BoschAnalyticsParameter,
    BoschAudioEncoder,
    BoschAudioEncoderOption,
    BoschAudioOutput,
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
        self.audio_encoders: list[BoschAudioEncoder] = []
        self.audio_outputs: list[BoschAudioOutput] = []
        self.analytics_parameters: list[BoschAnalyticsParameter] = []
        self._analytics_configuration_tokens: list[str] = []
        self.recording_supported = False
        self.recording_count = 0
        self.recording_job_count = 0
        self.replay_supported = False
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
        await self._async_load_audio()
        await self._async_load_analytics()
        await self._async_load_recording()
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

    async def _async_load_audio(self) -> None:
        """Discover audio encoder and physical output controls."""
        with suppress(Exception):
            media = await self.device.create_media_service()
            raw_encoders = await media.GetAudioEncoderConfigurations()
            encoders: list[BoschAudioEncoder] = []
            for raw_encoder in raw_encoders or []:
                token = str(_value(raw_encoder, "token", ""))
                if not token:
                    continue
                raw_options = await media.GetAudioEncoderConfigurationOptions(
                    {"ConfigurationToken": token}
                )
                options: dict[str, BoschAudioEncoderOption] = {}
                for raw_option in _value(raw_options, "Options", []) or []:
                    encoding = str(_value(raw_option, "Encoding", ""))
                    if not encoding:
                        continue
                    bitrates = _value(
                        _value(raw_option, "BitrateList"), "Items", []
                    ) or []
                    sample_rates = _value(
                        _value(raw_option, "SampleRateList"), "Items", []
                    ) or []
                    options[encoding] = BoschAudioEncoderOption(
                        encoding=encoding,
                        bitrates=tuple(int(value) for value in bitrates),
                        sample_rates=tuple(int(value) for value in sample_rates),
                    )
                if options:
                    encoders.append(BoschAudioEncoder(token, options))
            self.audio_encoders = encoders

        with suppress(Exception):
            deviceio = await self.device.create_deviceio_service()
            raw_outputs = await deviceio.GetAudioOutputs()
            outputs: list[BoschAudioOutput] = []
            for raw_output in raw_outputs or []:
                output_token = str(_value(raw_output, "token", ""))
                if not output_token:
                    continue
                raw_configuration = await deviceio.GetAudioOutputConfiguration(
                    {"AudioOutputToken": output_token}
                )
                configuration = _value(
                    raw_configuration,
                    "AudioOutputConfiguration",
                    raw_configuration,
                )
                configuration_token = str(_value(configuration, "token", ""))
                raw_options = await deviceio.GetAudioOutputConfigurationOptions(
                    {"AudioOutputToken": output_token}
                )
                options = _value(raw_options, "AudioOutputOptions", raw_options)
                level_range = _value(options, "OutputLevelRange")
                if not configuration_token or level_range is None:
                    continue
                outputs.append(
                    BoschAudioOutput(
                        configuration_token=configuration_token,
                        output_token=output_token,
                        minimum=int(_value(level_range, "Min", 0)),
                        maximum=int(_value(level_range, "Max", 0)),
                    )
                )
            self.audio_outputs = outputs

    async def _async_load_analytics(self) -> None:
        """Discover readable parameters from active analytics modules."""
        with suppress(Exception):
            media = await self.device.create_media_service()
            raw_configurations = await media.GetVideoAnalyticsConfigurations()
            tokens = [
                str(token)
                for configuration in raw_configurations or []
                if (token := _value(configuration, "token"))
            ]
            analytics = await self.device.create_analytics_service()
            parameters: list[BoschAnalyticsParameter] = []
            for token in tokens:
                modules = await analytics.GetAnalyticsModules(
                    {"ConfigurationToken": token}
                )
                for module in modules or []:
                    module_name = str(_value(module, "Name", ""))
                    raw_parameters = _value(
                        _value(module, "Parameters"),
                        "SimpleItem",
                        [],
                    )
                    for parameter in raw_parameters or []:
                        name = str(_value(parameter, "Name", ""))
                        if name not in {"Mode", "AnalysisType"}:
                            continue
                        parameters.append(
                            BoschAnalyticsParameter(
                                key=f"{token}\0{module_name}\0{name}",
                                name=name,
                            )
                        )
            self._analytics_configuration_tokens = tokens
            self.analytics_parameters = parameters

    async def _async_load_recording(self) -> None:
        """Inventory optional ONVIF recording and replay services."""
        with suppress(Exception):
            await self._async_update_recording_counts()
            self.recording_supported = True
        with suppress(Exception):
            replay = await self.device.create_replay_service()
            await replay.GetServiceCapabilities()
            self.replay_supported = True

    async def _async_update_recording_counts(self) -> None:
        """Refresh mutable ONVIF recording inventory counts."""
        recording = await self.device.create_recording_service()
        recordings = await recording.GetRecordings()
        jobs = await recording.GetRecordingJobs()
        self.recording_count = len(_value(recordings, "RecordingItem", []) or [])
        self.recording_job_count = len(_value(jobs, "JobItem", []) or [])

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
        if self.audio_encoders:
            media = await self.device.create_media_service()
            for encoder in self.audio_encoders:
                raw_configuration = await media.GetAudioEncoderConfiguration(
                    {"ConfigurationToken": encoder.token}
                )
                configuration = _value(
                    raw_configuration,
                    "Configuration",
                    raw_configuration,
                )
                state.audio_encoders[encoder.token] = {
                    "encoding": str(_value(configuration, "Encoding", "")),
                    "bitrate": int(_value(configuration, "Bitrate", 0)),
                    "sample_rate": int(_value(configuration, "SampleRate", 0)),
                }
        if self.audio_outputs:
            deviceio = await self.device.create_deviceio_service()
            for output in self.audio_outputs:
                raw_configuration = await deviceio.GetAudioOutputConfiguration(
                    {"AudioOutputToken": output.output_token}
                )
                configuration = _value(
                    raw_configuration,
                    "AudioOutputConfiguration",
                    raw_configuration,
                )
                state.audio_output_levels[output.configuration_token] = int(
                    _value(configuration, "OutputLevel", 0)
                )
        if self.analytics_parameters:
            analytics = await self.device.create_analytics_service()
            current: dict[str, str] = {}
            for token in self._analytics_configuration_tokens:
                modules = await analytics.GetAnalyticsModules(
                    {"ConfigurationToken": token}
                )
                for module in modules or []:
                    module_name = str(_value(module, "Name", ""))
                    raw_parameters = _value(
                        _value(module, "Parameters"),
                        "SimpleItem",
                        [],
                    )
                    for parameter in raw_parameters or []:
                        name = str(_value(parameter, "Name", ""))
                        if name in {"Mode", "AnalysisType"}:
                            current[f"{token}\0{module_name}\0{name}"] = str(
                                _value(parameter, "Value", "")
                            )
            state.analytics = current
        if self.recording_supported:
            await self._async_update_recording_counts()
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

    async def async_set_audio_encoder(
        self,
        token: str,
        setting: str,
        option: str,
    ) -> None:
        """Persist one validated audio encoder field."""
        encoder = next(
            (item for item in self.audio_encoders if item.token == token),
            None,
        )
        if encoder is None:
            raise ValueError("Unknown audio encoder token")
        media = await self.device.create_media_service()
        raw_configuration = await media.GetAudioEncoderConfiguration(
            {"ConfigurationToken": token}
        )
        configuration = _value(raw_configuration, "Configuration", raw_configuration)
        current_encoding = str(_value(configuration, "Encoding", ""))
        encoding, bitrate, sample_rate = validated_audio_values(
            encoder,
            current_encoding,
            int(_value(configuration, "Bitrate", 0)),
            int(_value(configuration, "SampleRate", 0)),
            setting,
            option,
        )
        configuration.Encoding = encoding
        configuration.Bitrate = bitrate
        configuration.SampleRate = sample_rate

        await media.SetAudioEncoderConfiguration(
            {
                "Configuration": configuration,
                "ForcePersistence": True,
            }
        )

    async def async_set_audio_output_level(self, token: str, level: int) -> None:
        """Persist a validated physical audio output level."""
        output = next(
            (
                item
                for item in self.audio_outputs
                if item.configuration_token == token
            ),
            None,
        )
        if output is None:
            raise ValueError("Unknown audio output token")
        if not output.minimum <= level <= output.maximum:
            raise ValueError("Audio output level is outside the supported range")
        deviceio = await self.device.create_deviceio_service()
        raw_configuration = await deviceio.GetAudioOutputConfiguration(
            {"AudioOutputToken": output.output_token}
        )
        configuration = _value(
            raw_configuration,
            "AudioOutputConfiguration",
            raw_configuration,
        )
        configuration.OutputLevel = level
        await deviceio.SetAudioOutputConfiguration(
            {
                "Configuration": configuration,
                "ForcePersistence": True,
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
            "audio_encoder_count": len(self.audio_encoders),
            "audio_output_count": len(self.audio_outputs),
            "analytics_parameter_count": len(self.analytics_parameters),
            "recording_supported": self.recording_supported,
            "recording_count": self.recording_count,
            "recording_job_count": self.recording_job_count,
            "replay_supported": self.replay_supported,
            "bicom_capabilities": sorted(self.bicom_objects),
            "service_namespaces": sorted(self.service_namespaces),
        }

    async def async_close(self) -> None:
        """Close ONVIF transports."""
        await self.device.close()
