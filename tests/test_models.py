"""Tests for stable multi-version camera identity."""

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _models_module():
    path = Path(__file__).parents[1] / "custom_components/bosch_video/models.py"
    spec = spec_from_file_location("bosch_video_models_identity_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_device_matches_serial_or_mac() -> None:
    """A camera remains the same when a later probe discovers its MAC."""
    models = _models_module()
    info = models.BoschDeviceInfo(
        manufacturer="Bosch",
        model="Camera",
        firmware_version="1",
        serial_number="serial-identifier",
        mac_address="00:11:22:33:44:55",
    )

    assert info.matches_unique_id("serial-identifier")
    assert info.matches_unique_id("00:11:22:33:44:55")
    assert not info.matches_unique_id("different-camera")
