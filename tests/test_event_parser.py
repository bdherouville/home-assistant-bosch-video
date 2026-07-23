"""Tests for Bosch ONVIF event normalization."""

import asyncio
from types import ModuleType, SimpleNamespace


def _item(name: str, value: str) -> SimpleNamespace:
    return SimpleNamespace(Name=name, Value=value)


def _message(
    topic: str,
    source_name: str,
    source_value: str,
    data_name: str,
    data_value: str,
) -> SimpleNamespace:
    payload = SimpleNamespace(
        Source=SimpleNamespace(
            SimpleItem=[_item(source_name, source_value)],
        ),
        Data=SimpleNamespace(
            SimpleItem=[_item(data_name, data_value)],
        ),
    )
    return SimpleNamespace(
        Topic=SimpleNamespace(_value_1=topic),
        Message=SimpleNamespace(_value_1=payload),
    )


def test_bosch_motion_alarm_extension_is_parsed(
    event_parser_module: ModuleType,
) -> None:
    """Bosch MotionAlarm is supported even though it is not in onvif_parsers."""
    message = _message(
        "tns1:VideoSource/MotionAlarm",
        "Source",
        "private-source-token",
        "State",
        "true",
    )

    events = asyncio.run(event_parser_module.async_parse_event("camera-id", message))

    assert len(events) == 1
    assert events[0].name == "Motion alarm"
    assert events[0].device_class == "motion"
    assert events[0].value is True
    assert "private-source-token" not in events[0].uid


def test_standard_digital_input_is_normalized(event_parser_module: ModuleType) -> None:
    """A standard ONVIF topic uses the upstream parser with a private-safe ID."""
    message = _message(
        "tns1:Device/Trigger/DigitalInput",
        "InputToken",
        "private-input-token",
        "LogicalState",
        "true",
    )

    events = asyncio.run(event_parser_module.async_parse_event("camera-id", message))

    assert len(events) == 1
    assert events[0].name == "Digital Input"
    assert events[0].value is True
    assert "private-input-token" not in events[0].uid


def test_unknown_topic_is_ignored(event_parser_module: ModuleType) -> None:
    """Unsupported vendor topics cannot break the subscription loop."""
    message = _message(
        "tns1:Vendor/Unknown",
        "Source",
        "value",
        "State",
        "true",
    )

    assert (
        asyncio.run(event_parser_module.async_parse_event("camera-id", message))
        == []
    )


def test_identical_sources_on_two_cameras_have_distinct_ids(
    event_parser_module: ModuleType,
) -> None:
    """Multi-camera event entities cannot collide in the registry."""
    message = _message(
        "tns1:VideoSource/MotionAlarm",
        "Source",
        "same-source-token",
        "State",
        "true",
    )

    first = asyncio.run(event_parser_module.async_parse_event("camera-a", message))
    second = asyncio.run(event_parser_module.async_parse_event("camera-b", message))

    assert first[0].uid != second[0].uid
