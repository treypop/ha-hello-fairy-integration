""" light platform """
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.color import color_hs_to_RGB, color_RGB_to_hs

from .const import DOMAIN
from .hello_fairy import BleakError, Lamp

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice

_LOGGER = logging.getLogger(__name__)

# Replaces the broken SUPPORT_ constants
SUPPORT_FEATURES = LightEntityFeature.EFFECT
COLOR_MODES = {ColorMode.RGB}

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the platform from config_entry."""
    _LOGGER.debug(
        f"light async_setup_entry: setting up the config entry {config_entry.title}"
    )
    name = config_entry.data.get(CONF_NAME) or DOMAIN
    ble_device = hass.data[DOMAIN][config_entry.entry_id]

    entity = HelloFairyBT(name, ble_device)
    async_add_entities([entity])


class HelloFairyBT(LightEntity):
    """Representation of a light."""

    # Modern attributes for 2026 compatibility
    _attr_supported_color_modes = COLOR_MODES
    _attr_color_mode = ColorMode.RGB
    _attr_supported_features = SUPPORT_FEATURES

    def __init__(self, name: str, ble_device: BLEDevice) -> None:
        """Initialize the light."""
        self._name = name
        self._mac = ble_device.address
        self._is_on = False
        self._rgb = (0, 0, 0)
        self._brightness = 0
        self._effect_list = ["flow", "none"]
        self._effect = "none"
        self._available = True

        _LOGGER.info(f"Initializing Hello Fairy Entity: {self._name}, {self._mac}")
        self._dev = Lamp(ble_device)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self.async_on_remove(
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, self.async_will_remove_from_hass
            )
        )
        self.async_schedule_update_ha_state(force_refresh=True)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        try:
            await self._dev.disconnect()
        except Exception:
            _LOGGER.debug("Exception disconnecting", exc_info=True)

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self._name,
            "manufacturer": "HelloFairy",
            "model": "Bluetooth Fairy Lights",
        }

    @property
    def unique_id(self) -> str:
        return self._mac

    @property
    def available(self) -> bool:
        return self._available

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def name(self) -> str:
        return self._name

    @property
    def brightness(self) -> int:
        return self._brightness

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        """Return the rgb color value."""
        return self._rgb

    @property
    def effect_list(self):
        return self._effect_list

    @property
    def effect(self):
        return self._effect

    @property
    def is_on(self) -> bool:
        return self._is_on

    async def async_update(self) -> None:
        try:
            await self._dev.get_state()
        except Exception as ex:
            _LOGGER.error(f"Fail requesting the light status: {ex}")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        
        # Handle Brightness
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            if brightness == 0:
                await self.async_turn_off()
                return
            self._brightness = brightness
        else:
            brightness = self._brightness or 255

        brightness_dev = int(round(brightness * 100 / 255))

        if not self._is_on:
            await self._dev.turn_on()
            self._is_on = True

        # Handle Color
        if ATTR_RGB_COLOR in kwargs:
            self._rgb = kwargs[ATTR_RGB_COLOR]
            await self._dev.set_color(*self._rgb, brightness=brightness_dev)
            await asyncio.sleep(0.5)
            return

        # Handle just Brightness change
        if ATTR_BRIGHTNESS in kwargs:
            await self._dev.set_brightness(brightness_dev)
            return

        # Handle Effect
        if ATTR_EFFECT in kwargs:
            self._effect = kwargs[ATTR_EFFECT]
            # Add specific effect call here if your hello_fairy.py supports it

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._dev.turn_off()
        self._is_on = False
