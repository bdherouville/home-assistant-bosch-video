"""Parse ONVIF notifications exposed by Bosch cameras."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

import onvif_parsers
from onvif_parsers.errors import UnknownTopicError


@dataclass(slots=True, frozen=True)
class BoschOnvifEvent:
    """One normalized ONVIF event."""

    uid: str
    name: str
    platform: str
    device_class: str | None
    value: Any
    entity_enabled: bool = True


def _value(obj: Any, name: str, default: Any = None) -> Any:
    """Read a Zeep object or mapping."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def event_topic(message: Any) -> str:
    """Return a canonical topic string."""
    topic = _value(_value(message, "Topic"), "_value_1", "")
    return str(topic).rstrip("/.")


def _simple_items(container: Any) -> list[tuple[str, str]]:
    """Return ONVIF SimpleItem name/value pairs."""
    items = _value(container, "SimpleItem", []) or []
    return [
        (str(_value(item, "Name", "")), str(_value(item, "Value", "")))
        for item in items
    ]


def _event_uid(
    camera_uid: str,
    topic: str,
    source_uid: str,
    event_index: int = 0,
) -> str:
    """Build a stable ID without exposing ONVIF source tokens."""
    digest = sha256(
        f"{topic}\0{source_uid}\0{event_index}".encode()
    ).hexdigest()[:16]
    topic_name = topic.rsplit("/", 1)[-1].replace(":", "_")
    return f"{camera_uid}#event#{topic_name}#{digest}"


def _bosch_motion_alarm(camera_uid: str, topic: str, message: Any) -> BoschOnvifEvent:
    """Parse the Bosch VideoSource/MotionAlarm extension."""
    payload = _value(_value(message, "Message"), "_value_1")
    source = _simple_items(_value(payload, "Source"))
    data = _simple_items(_value(payload, "Data"))
    state = next((value for name, value in data if name == "State"), "")
    source_uid = "\0".join(f"{name}={value}" for name, value in source)
    return BoschOnvifEvent(
        uid=_event_uid(camera_uid, topic, source_uid),
        name="Motion alarm",
        platform="binary_sensor",
        device_class="motion",
        value=state.casefold() in {"1", "active", "on", "true"},
    )


async def async_parse_event(
    camera_uid: str, message: Any
) -> list[BoschOnvifEvent]:
    """Parse a standard ONVIF event or a known Bosch extension."""
    topic = event_topic(message)
    if not topic:
        return []

    if topic == "tns1:VideoSource/MotionAlarm":
        return [_bosch_motion_alarm(camera_uid, topic, message)]

    try:
        parsed_events = await onvif_parsers.parse(topic, camera_uid, message)
    except UnknownTopicError:
        return []

    return [
        BoschOnvifEvent(
            uid=_event_uid(camera_uid, topic, event.uid, index),
            name=event.name,
            platform=event.platform,
            device_class=event.device_class,
            value=event.value,
            entity_enabled=event.entity_enabled,
        )
        for index, event in enumerate(parsed_events)
    ]
