"""Bosch BICOM framing transported through the RCP XML gateway."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum

from .rcp import BoschRcpClient, RcpDataType

RCP_BICOM_COMMAND = 0x09A5
DEFAULT_FLAGS = 0x85
BICOM_ERROR_ACTION = 0x6F


class BicomServer(IntEnum):
    """Known Bosch BICOM servers."""

    DEVICE = 2
    CAMERA = 4
    PTZ_LENS = 6
    CONTENT_ANALYSIS = 8
    IO = 10
    VCA = 12


class BicomAction(IntEnum):
    """BICOM object operations."""

    GET = 0x01
    SET = 0x03
    SET_DEFAULT = 0x08
    GET_MAX = 0x0B
    GET_MIN = 0x0C
    GET_OPTIONS = 0x0D


class BicomValueType(StrEnum):
    """Value encodings used by the Bosch web client."""

    NUMBER = "number"
    UNSIGNED_NUMBER = "usnumber"
    ULONG = "ulong"
    INT = "int"
    BYTE = "byte"
    BYTES = "bytes"


class BicomError(Exception):
    """Base BICOM error."""


class BicomProtocolError(BicomError):
    """Malformed or mismatched BICOM response."""


class BicomObjectError(BicomError):
    """The camera rejected a BICOM object operation."""

    def __init__(self, code: int) -> None:
        """Initialize the object error."""
        self.code = code
        super().__init__(f"The camera returned BICOM error 0x{code:04x}")


@dataclass(slots=True, frozen=True)
class BicomObject:
    """Known object metadata and validation bounds."""

    server: BicomServer
    object_id: int
    value_type: BicomValueType = BicomValueType.NUMBER
    minimum: int | None = None
    maximum: int | None = None


@dataclass(slots=True, frozen=True)
class BicomResponse:
    """Decoded BICOM response."""

    server: int
    object_id: int
    action: int
    flags: int
    raw_value: bytes
    value: int | bytes


KNOWN_OBJECTS: dict[str, BicomObject] = {
    "day_night_mode": BicomObject(
        BicomServer.CAMERA,
        320,
        minimum=0,
        maximum=2,
    ),
    "auto_iris": BicomObject(BicomServer.CAMERA, 432),
    "auto_iris_level": BicomObject(BicomServer.CAMERA, 434),
    "digital_zoom": BicomObject(BicomServer.CAMERA, 464),
    "focus_mode": BicomObject(BicomServer.CAMERA, 496),
    "focus_speed": BicomObject(BicomServer.CAMERA, 498),
    "near_limit_day": BicomObject(BicomServer.CAMERA, 501),
    "near_limit_night": BicomObject(BicomServer.CAMERA, 503),
    "ir_illuminator": BicomObject(
        BicomServer.CAMERA,
        1040,
        minimum=0,
        maximum=2,
    ),
    "ir_intensity": BicomObject(
        BicomServer.CAMERA,
        1041,
        minimum=0,
        maximum=30,
    ),
    "ir_focus_correction": BicomObject(BicomServer.CAMERA, 1043),
    "maximum_zoom_speed": BicomObject(BicomServer.PTZ_LENS, 289),
    "zoom_limit": BicomObject(BicomServer.PTZ_LENS, 297),
}


def encode_bicom_payload(
    obj: BicomObject,
    action: BicomAction,
    value: int | bytes | None = None,
    *,
    flags: int = DEFAULT_FLAGS,
) -> str:
    """Encode a BICOM request as the hexadecimal RCP payload."""
    if not 0x80 <= flags <= 0xFF:
        raise ValueError("BICOM flags must contain the format marker")
    if not 0 <= obj.object_id <= 0xFFFF:
        raise ValueError("BICOM object id must fit in 16 bits")
    payload = bytearray((flags,))
    payload.extend(int(obj.server).to_bytes(2, "big"))
    payload.extend(obj.object_id.to_bytes(2, "big"))
    payload.append(int(action))
    if value is not None:
        payload.extend(_encode_value(value, obj.value_type))
    return f"0x{payload.hex()}"


def _encode_value(value: int | bytes, value_type: BicomValueType) -> bytes:
    """Encode one BICOM value."""
    if value_type is BicomValueType.BYTES:
        if not isinstance(value, bytes):
            raise TypeError("A bytes BICOM object requires bytes")
        return value
    if not isinstance(value, int):
        raise TypeError("A numeric BICOM object requires an integer")
    sizes = {
        BicomValueType.NUMBER: 2,
        BicomValueType.UNSIGNED_NUMBER: 2,
        BicomValueType.ULONG: 4,
        BicomValueType.INT: 4,
        BicomValueType.BYTE: 1,
    }
    signed = value_type in {BicomValueType.NUMBER, BicomValueType.INT}
    try:
        return value.to_bytes(sizes[value_type], "big", signed=signed)
    except OverflowError as err:
        raise ValueError("BICOM value does not fit its declared type") from err


def decode_bicom_response(
    text: str,
    obj: BicomObject,
    value_type: BicomValueType | None = None,
) -> BicomResponse:
    """Decode a hexadecimal P_OCTET RCP result."""
    normalized = text.strip().removeprefix("0x").replace(" ", "").replace("\n", "")
    try:
        packet = bytes.fromhex(normalized)
    except ValueError as err:
        raise BicomProtocolError("BICOM response is not hexadecimal") from err
    if len(packet) < 6:
        raise BicomProtocolError("BICOM response is shorter than its header")

    flags = packet[0]
    if flags & 0x08:
        if len(packet) < 12:
            raise BicomProtocolError("BICOM lease-time response is truncated")
        packet = packet[:1] + packet[7:]

    server = int.from_bytes(packet[1:3], "big")
    object_id = int.from_bytes(packet[3:5], "big")
    action = packet[5]
    raw_value = packet[6:]
    if action == BICOM_ERROR_ACTION:
        code = int.from_bytes(raw_value or b"\x00", "big")
        raise BicomObjectError(code)
    if server != int(obj.server) or object_id != obj.object_id:
        raise BicomProtocolError("BICOM response does not match the requested object")

    data_type = value_type or obj.value_type
    if data_type is BicomValueType.BYTES:
        value: int | bytes = raw_value
    else:
        signed = data_type in {BicomValueType.NUMBER, BicomValueType.INT}
        value = int.from_bytes(raw_value, "big", signed=signed)
    return BicomResponse(server, object_id, action, flags, raw_value, value)


class BoschBicomClient:
    """Read and write known BICOM objects through RCP."""

    def __init__(self, rcp: BoschRcpClient) -> None:
        """Initialize the client."""
        self._rcp = rcp

    async def async_get(
        self,
        obj: BicomObject,
        *,
        action: BicomAction = BicomAction.GET,
        value_type: BicomValueType | None = None,
    ) -> BicomResponse:
        """Read a value, bound or option list."""
        if action not in {
            BicomAction.GET,
            BicomAction.GET_MIN,
            BicomAction.GET_MAX,
            BicomAction.GET_OPTIONS,
        }:
            raise ValueError("async_get only accepts a read-only BICOM action")
        payload = encode_bicom_payload(obj, action)
        result = await self._rcp.async_write(
            RCP_BICOM_COMMAND,
            RcpDataType.OCTETS,
            payload,
        )
        return decode_bicom_response(result.value, obj, value_type)

    async def async_set(self, obj: BicomObject, value: int | bytes) -> BicomResponse:
        """Set a validated known BICOM object."""
        if isinstance(value, int):
            if obj.minimum is not None and value < obj.minimum:
                raise ValueError("BICOM value is below the validated minimum")
            if obj.maximum is not None and value > obj.maximum:
                raise ValueError("BICOM value is above the validated maximum")
        payload = encode_bicom_payload(obj, BicomAction.SET, value)
        result = await self._rcp.async_write(
            RCP_BICOM_COMMAND,
            RcpDataType.OCTETS,
            payload,
        )
        return decode_bicom_response(result.value, obj)
