"""Switch platform for Bosch Video relay outputs."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BoschVideoConfigEntry, BoschVideoCoordinator
from .entity import BoschVideoEntity
from .models import BoschRelay


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoschVideoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ONVIF relay switches."""
    coordinator = entry.runtime_data
    async_add_entities(
        BoschRelaySwitch(coordinator, relay) for relay in coordinator.client.relays
    )


class BoschRelaySwitch(BoschVideoEntity, SwitchEntity):
    """Optimistic control for a physical camera relay."""

    _attr_translation_key = "relay"

    def __init__(
        self,
        coordinator: BoschVideoCoordinator,
        relay: BoschRelay,
    ) -> None:
        """Initialize a relay."""
        super().__init__(coordinator)
        self.relay = relay
        self._attr_is_on = False
        camera_id = coordinator.client.info.unique_id
        self._attr_unique_id = f"{camera_id}#relay#{relay.token}"
        self._attr_translation_placeholders = {"token": relay.token}

    async def async_turn_on(self, **kwargs: object) -> None:
        """Activate the relay."""
        await self.coordinator.client.async_set_relay(self.relay.token, True)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: object) -> None:
        """Deactivate the relay."""
        await self.coordinator.client.async_set_relay(self.relay.token, False)
        self._attr_is_on = False
        self.async_write_ha_state()
