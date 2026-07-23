"""Tests for Bosch BICOM framing."""

import pytest


def test_encode_get_payload(protocol_modules):
    """A read packet follows the web client's six-byte header."""
    bicom = protocol_modules["bicom"]
    obj = bicom.BicomObject(bicom.BicomServer.CAMERA, 320)

    payload = bicom.encode_bicom_payload(obj, bicom.BicomAction.GET)

    assert payload == "0x850004014001"


def test_encode_signed_number(protocol_modules):
    """Signed NUMBER values use two-byte big-endian encoding."""
    bicom = protocol_modules["bicom"]
    obj = bicom.BicomObject(bicom.BicomServer.CAMERA, 434)

    payload = bicom.encode_bicom_payload(obj, bicom.BicomAction.SET, -2)

    assert payload == "0x85000401b203fffe"


def test_decode_numeric_response(protocol_modules):
    """Response headers are checked before a value is decoded."""
    bicom = protocol_modules["bicom"]
    obj = bicom.BicomObject(bicom.BicomServer.CAMERA, 320)

    response = bicom.decode_bicom_response("85 00 04 01 40 01 00 02", obj)

    assert response.server == 4
    assert response.object_id == 320
    assert response.value == 2


def test_decode_object_error(protocol_modules):
    """BICOM error action 0x6f exposes the two-byte object error."""
    bicom = protocol_modules["bicom"]
    obj = bicom.BicomObject(bicom.BicomServer.CAMERA, 320)

    with pytest.raises(bicom.BicomObjectError) as raised:
        bicom.decode_bicom_response("85 00 04 01 40 6f 00 10", obj)

    assert raised.value.code == 0x10


def test_response_for_another_object_is_rejected(protocol_modules):
    """A response cannot silently update the wrong entity."""
    bicom = protocol_modules["bicom"]
    obj = bicom.BicomObject(bicom.BicomServer.CAMERA, 320)

    with pytest.raises(bicom.BicomProtocolError):
        bicom.decode_bicom_response("85 00 04 01 f0 01 00 01", obj)


def test_auto_iris_has_verified_boolean_bounds(protocol_modules):
    """The iris mode cannot accept a value absent from the Bosch WebGUI."""
    bicom = protocol_modules["bicom"]
    obj = bicom.KNOWN_OBJECTS["auto_iris"]

    assert obj.minimum == 0
    assert obj.maximum == 1
