"""Test fixtures that load the standalone protocol module."""

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture(scope="session")
def rcp_module():
    """Load rcp.py without importing the Home Assistant package initializer."""
    path = Path(__file__).parents[1] / "custom_components" / "bosch_video" / "rcp.py"
    spec = spec_from_file_location("bosch_video_rcp_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def protocol_modules():
    """Load RCP and BICOM as a small standalone protocol package."""
    source = Path(__file__).parents[1] / "custom_components" / "bosch_video"
    package_name = "bosch_video_protocol_test"
    package = ModuleType(package_name)
    package.__path__ = [str(source)]
    sys.modules[package_name] = package

    modules = {}
    for name in ("rcp", "bicom"):
        spec = spec_from_file_location(
            f"{package_name}.{name}",
            source / f"{name}.py",
        )
        assert spec is not None
        assert spec.loader is not None
        module = module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        modules[name] = module
    return modules


@pytest.fixture(scope="session")
def event_parser_module():
    """Load event_parser.py without importing the integration initializer."""
    path = (
        Path(__file__).parents[1]
        / "custom_components"
        / "bosch_video"
        / "event_parser.py"
    )
    spec = spec_from_file_location("bosch_video_event_parser_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def audio_modules():
    """Load pure audio validation code without Home Assistant."""
    source = Path(__file__).parents[1] / "custom_components" / "bosch_video"
    package_name = "bosch_video_audio_test"
    package = ModuleType(package_name)
    package.__path__ = [str(source)]
    sys.modules[package_name] = package

    modules = {}
    for name in ("models", "audio"):
        spec = spec_from_file_location(
            f"{package_name}.{name}",
            source / f"{name}.py",
        )
        assert spec is not None
        assert spec.loader is not None
        module = module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        modules[name] = module
    return modules
