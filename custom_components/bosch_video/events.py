"""Reliable ONVIF PullPoint event subscription for Bosch cameras."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from onvif import ONVIFCamera
from onvif.client import PullPointManager
from onvif.exceptions import ONVIFError
from onvif.util import stringify_onvif_error
from zeep.exceptions import Fault, TransportError, ValidationError, XMLParseError

from .const import LOGGER
from .event_parser import BoschOnvifEvent, async_parse_event, event_topic

SUBSCRIPTION_TIME = timedelta(minutes=10)
PULL_TIMEOUT = timedelta(seconds=60)
MESSAGE_LIMIT = 100
POLL_COOLDOWN = 0.75
RECONNECT_DELAY = 15

EVENT_ERRORS = (
    ONVIFError,
    Fault,
    TransportError,
    ValidationError,
    XMLParseError,
    aiohttp.ClientError,
    TimeoutError,
)


def _value(obj: Any, name: str, default: Any = None) -> Any:
    """Read a Zeep object or mapping."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class BoschEventManager:
    """Maintain one PullPoint subscription and normalized event state."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: ONVIFCamera,
        camera_uid: str,
        name: str,
    ) -> None:
        """Initialize the event manager without network I/O."""
        self._hass = hass
        self._device = device
        self._camera_uid = camera_uid
        self._name = name
        self._manager: PullPointManager | None = None
        self._task: asyncio.Task[None] | None = None
        self._listeners: list[CALLBACK_TYPE] = []
        self._events: dict[str, BoschOnvifEvent] = {}
        self._unknown_topics: set[str] = set()
        self._stopping = False

    @property
    def started(self) -> bool:
        """Return whether the background event loop is active."""
        return self._task is not None and not self._task.done()

    def get_uid(self, uid: str) -> BoschOnvifEvent | None:
        """Return one current event."""
        return self._events.get(uid)

    def get_platform(self, platform: str) -> list[BoschOnvifEvent]:
        """Return current events belonging to a Home Assistant platform."""
        return [
            event for event in self._events.values() if event.platform == platform
        ]

    def diagnostics(self) -> dict[str, Any]:
        """Return subscription statistics without event or source identifiers."""
        platform_counts: dict[str, int] = {}
        for event in self._events.values():
            platform_counts[event.platform] = platform_counts.get(event.platform, 0) + 1
        return {
            "pullpoint_started": self.started,
            "event_counts": platform_counts,
            "unsupported_topic_count": len(self._unknown_topics),
        }

    @callback
    def async_add_listener(self, listener: CALLBACK_TYPE) -> Callable[[], None]:
        """Register a callback for state and discovery changes."""
        self._listeners.append(listener)

        @callback
        def remove_listener() -> None:
            """Remove the callback."""
            with suppress(ValueError):
                self._listeners.remove(listener)

        return remove_listener

    @callback
    def _async_notify_listeners(self) -> None:
        """Notify entity platforms of changed event data."""
        for listener in self._listeners:
            listener()

    @callback
    def _async_mark_stale(self) -> None:
        """Mark event values unavailable after a lost subscription."""
        if not self._events:
            return
        self._events = {
            uid: BoschOnvifEvent(
                uid=event.uid,
                name=event.name,
                platform=event.platform,
                device_class=event.device_class,
                value=None,
                entity_enabled=event.entity_enabled,
            )
            for uid, event in self._events.items()
        }
        self._async_notify_listeners()

    async def async_start(self) -> bool:
        """Start event reception without trusting the advertised capability flag."""
        if self.started:
            return True
        self._stopping = False
        try:
            await self._async_create_subscription()
        except EVENT_ERRORS as err:
            LOGGER.debug(
                "%s: PullPoint is initially unavailable: %s",
                self._name,
                stringify_onvif_error(err),
            )
        self._task = self._hass.async_create_background_task(
            self._async_run(),
            f"{self._name} Bosch ONVIF events",
        )
        return self._manager is not None

    async def async_stop(self) -> None:
        """Stop polling and unsubscribe so the camera does not leak subscriptions."""
        self._stopping = True
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        await self._async_shutdown_subscription()
        self._listeners.clear()

    async def _async_create_subscription(self) -> None:
        """Create and synchronize a new PullPoint subscription."""
        await self._async_shutdown_subscription()
        manager = await self._device.create_pullpoint_manager(
            SUBSCRIPTION_TIME,
            self._async_mark_stale,
        )
        try:
            await manager.set_synchronization_point()
        except asyncio.CancelledError:
            with suppress(*EVENT_ERRORS):
                await manager.shutdown()
            raise
        except EVENT_ERRORS:
            with suppress(*EVENT_ERRORS):
                await manager.shutdown()
            raise
        self._manager = manager
        LOGGER.debug("%s: Bosch PullPoint subscription started", self._name)

    async def _async_shutdown_subscription(self) -> None:
        """Best-effort unsubscribe from the current subscription."""
        manager = self._manager
        self._manager = None
        if manager is None or manager.closed:
            return
        try:
            await manager.shutdown()
        except EVENT_ERRORS as err:
            LOGGER.debug(
                "%s: PullPoint unsubscribe failed during cleanup: %s",
                self._name,
                stringify_onvif_error(err),
            )

    async def _async_run(self) -> None:
        """Continuously pull messages and recover after camera/network restarts."""
        while not self._stopping:
            if self._manager is None:
                try:
                    await self._async_create_subscription()
                except EVENT_ERRORS as err:
                    LOGGER.debug(
                        "%s: PullPoint reconnect failed: %s",
                        self._name,
                        stringify_onvif_error(err),
                    )
                    await asyncio.sleep(RECONNECT_DELAY)
                    continue

            try:
                await self._async_pull_messages()
            except asyncio.CancelledError:
                raise
            except EVENT_ERRORS as err:
                LOGGER.debug(
                    "%s: PullPoint read failed; recreating subscription: %s",
                    self._name,
                    stringify_onvif_error(err),
                )
                self._async_mark_stale()
                await self._async_shutdown_subscription()
                await asyncio.sleep(RECONNECT_DELAY)
                continue
            await asyncio.sleep(POLL_COOLDOWN)

    async def _async_pull_messages(self) -> None:
        """Fetch, parse, and publish one PullPoint response."""
        manager = self._manager
        if manager is None:
            return
        response = await manager.get_service().PullMessages(
            {
                "MessageLimit": MESSAGE_LIMIT,
                "Timeout": PULL_TIMEOUT,
            }
        )
        messages = _value(response, "NotificationMessage", []) or []
        changed = False
        for message in messages:
            parsed_events = await async_parse_event(self._camera_uid, message)
            if not parsed_events:
                topic = event_topic(message)
                if topic and topic not in self._unknown_topics:
                    self._unknown_topics.add(topic)
                    LOGGER.debug(
                        "%s: Unsupported ONVIF event topic: %s",
                        self._name,
                        topic,
                    )
                continue
            for event in parsed_events:
                if self._events.get(event.uid) != event:
                    self._events[event.uid] = event
                    changed = True
        if changed:
            self._async_notify_listeners()
