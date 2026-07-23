"""Tests for capability-constrained audio settings."""

from types import ModuleType

import pytest


def _encoder(modules: dict[str, ModuleType]):
    models = modules["models"]
    return models.BoschAudioEncoder(
        token="encoder",
        options={
            "G711": models.BoschAudioEncoderOption("G711", (64,), (8,)),
            "AAC": models.BoschAudioEncoderOption("AAC", (48, 80), (16,)),
        },
    )


def test_codec_change_selects_a_valid_combination(
    audio_modules: dict[str, ModuleType],
) -> None:
    """Changing codec also repairs incompatible bitrate and sample rate."""
    result = audio_modules["audio"].validated_audio_values(
        _encoder(audio_modules),
        "G711",
        64,
        8,
        "encoding",
        "AAC",
    )

    assert result == ("AAC", 48, 16)


def test_valid_bitrate_is_preserved(audio_modules: dict[str, ModuleType]) -> None:
    """A bitrate exposed for the active codec is accepted."""
    result = audio_modules["audio"].validated_audio_values(
        _encoder(audio_modules),
        "AAC",
        48,
        16,
        "bitrate",
        "80",
    )

    assert result == ("AAC", 80, 16)


def test_invalid_combination_is_rejected(
    audio_modules: dict[str, ModuleType],
) -> None:
    """A value from another codec cannot be sent to the camera."""
    with pytest.raises(ValueError, match="Unsupported audio bitrate"):
        audio_modules["audio"].validated_audio_values(
            _encoder(audio_modules),
            "G711",
            64,
            8,
            "bitrate",
            "80",
        )
