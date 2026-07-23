"""Pure validation helpers for ONVIF audio configuration."""

from __future__ import annotations

from .models import BoschAudioEncoder


def validated_audio_values(
    encoder: BoschAudioEncoder,
    current_encoding: str,
    current_bitrate: int,
    current_sample_rate: int,
    setting: str,
    option: str,
) -> tuple[str, int, int]:
    """Return a valid encoder tuple after changing one exposed field."""
    if current_encoding not in encoder.options:
        raise ValueError("The current audio encoding is not advertised")

    if setting == "encoding":
        if option not in encoder.options:
            raise ValueError("Unsupported audio encoding")
        selected = encoder.options[option]
        if not selected.bitrates or not selected.sample_rates:
            raise ValueError("The audio encoding has no usable options")
        return (
            option,
            (
                current_bitrate
                if current_bitrate in selected.bitrates
                else selected.bitrates[0]
            ),
            (
                current_sample_rate
                if current_sample_rate in selected.sample_rates
                else selected.sample_rates[0]
            ),
        )

    selected = encoder.options[current_encoding]
    if setting == "bitrate":
        value = int(option)
        if value not in selected.bitrates:
            raise ValueError("Unsupported audio bitrate")
        return current_encoding, value, current_sample_rate
    if setting == "sample_rate":
        value = int(option)
        if value not in selected.sample_rates:
            raise ValueError("Unsupported audio sample rate")
        return current_encoding, current_bitrate, value
    raise ValueError("Unknown audio encoder setting")
