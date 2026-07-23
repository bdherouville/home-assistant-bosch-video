"""Constants for the Bosch Video integration."""

import logging
from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "bosch_video"
LOGGER = logging.getLogger(__package__)

PLATFORMS: list[Platform] = [
    Platform.CAMERA,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

DEFAULT_NAME = "Bosch camera"
DEFAULT_PORT = 80
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

CONF_VERIFY_SSL = "verify_ssl"

ATTR_PROFILE_TOKEN = "profile_token"
ATTR_VIDEO_SOURCE_TOKEN = "video_source_token"
