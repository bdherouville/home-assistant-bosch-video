"""ONVIF event binary sensors for Bosch Video."""

from __future__ import annotations

from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.enum import try_parse_enum

from .coordinator import BoschVideoConfigEntry, BoschVideoCoordinator
from .entity import BoschVideoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoschVideoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up dynamically discovered PullPoint binary sensors."""
    coordinator = entry.runtime_data
    event_manager = coordinator.events
    added_uids: set[str] = set()

    @callback
    def async_discover_entities() -> None:
        """Add entities for event topics received after platform setup."""
        new_events = [
            event
            for event in event_manager.get_platform("binary_sensor")
            if event.uid not in added_uids
        ]
        if not new_events:
            return
        added_uids.update(event.uid for event in new_events)
        async_add_entities(
            BoschEventBinarySensor(coordinator, event.uid) for event in new_events
        )

    async_discover_entities()
    entry.async_on_unload(event_manager.async_add_listener(async_discover_entities))


class BoschEventBinarySensor(BoschVideoEntity, BinarySensorEntity):
    """A binary sensor backed by a Bosch ONVIF notification."""

    _attr_should_poll = False

    def __init__(self, coordinator: BoschVideoCoordinator, event_uid: str) -> None:
        """Initialize one event entity."""
        super().__init__(coordinator)
        event = coordinator.events.get_uid(event_uid)
        if event is None:
            raise RuntimeError("The ONVIF event is unavailable")
        self._event_uid = event_uid
        self._attr_unique_id = event.uid
        self._attr_name = event.name
        self._attr_device_class = try_parse_enum(
            BinarySensorDeviceClass, event.device_class
        )
        self._attr_entity_registry_enabled_default = event.entity_enabled

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the latest event state."""
        event = self.coordinator.events.get_uid(self._event_uid)
        return event.value if event is not None else None

    async def async_added_to_hass(self) -> None:
        """Subscribe this entity to event updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.events.async_add_listener(self.async_write_ha_state)
        )
