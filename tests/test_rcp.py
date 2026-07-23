"""Tests for Bosch RCP transport primitives."""

import hashlib

import pytest


def test_parse_digest_challenge(rcp_module):
    """Quoted values and qop lists are decoded."""
    result = rcp_module.parse_digest_challenge(
        'Digest realm="Bosch camera", nonce="abc123", '
        'qop="auth,auth-int", algorithm=MD5, opaque="xyz"'
    )

    assert result == {
        "realm": "Bosch camera",
        "nonce": "abc123",
        "qop": "auth,auth-int",
        "algorithm": "MD5",
        "opaque": "xyz",
    }


def test_digest_matches_rfc_2617_example(rcp_module):
    """The classic RFC Digest example produces the specified response."""
    header = rcp_module.build_digest_authorization(
        challenge={
            "realm": "testrealm@host.com",
            "nonce": "dcd98b7102dd2f0e8b11d0f600bfb0c093",
            "qop": "auth",
            "algorithm": "MD5",
            "opaque": "5ccc069c403ebaf9f0171e9517f40e41",
        },
        username="Mufasa",
        password="Circle Of Life",
        method="GET",
        request_target="/dir/index.html",
        nonce_count=1,
        cnonce="0a4f113b",
    )

    assert 'response="6629fae49393a05397450978507c4ef1"' in header
    assert "qop=auth" in header
    assert "nc=00000001" in header


def test_digest_without_qop(rcp_module):
    """RFC 2069-style challenges remain supported by older firmware."""
    header = rcp_module.build_digest_authorization(
        challenge={"realm": "camera", "nonce": "nonce", "algorithm": "MD5"},
        username="service",
        password="secret",
        method="GET",
        request_target="/rcp.xml?direction=READ",
        nonce_count=1,
        cnonce="unused",
    )
    ha1 = hashlib.md5(b"service:camera:secret", usedforsecurity=False).hexdigest()
    ha2 = hashlib.md5(b"GET:/rcp.xml?direction=READ", usedforsecurity=False).hexdigest()
    expected = hashlib.md5(
        f"{ha1}:nonce:{ha2}".encode(), usedforsecurity=False
    ).hexdigest()

    assert f'response="{expected}"' in header
    assert "qop=" not in header


def test_parse_successful_rcp_xml(rcp_module):
    """A successful response exposes metadata and value."""
    result = rcp_module.parse_rcp_xml(
        """
        <rcp>
          <auth>2</auth><protocol>TCP</protocol>
          <result><hex>0x00000003</hex><dec>3</dec></result>
        </rcp>
        """,
        0x09BF,
        rcp_module.RcpDataType.DWORD,
        "READ",
        1,
    )

    assert result.command == 0x09BF
    assert result.auth_level == 2
    assert result.protocol == "TCP"
    assert result.value == "3"
    assert result.hexadecimal == "0x00000003"
    assert result.decimal == 3


def test_parse_rcp_error(rcp_module):
    """RCP command errors retain their hexadecimal code."""
    with pytest.raises(rcp_module.RcpCommandError) as raised:
        rcp_module.parse_rcp_xml(
            "<rcp><result><err>0x90</err></result></rcp>",
            0x0C39,
            rcp_module.RcpDataType.OCTETS,
            "READ",
            1,
        )

    assert raised.value.code == "0x90"


def test_parse_octet_string_ignores_length_field(rcp_module):
    """P_OCTET returns its byte string rather than concatenated XML fields."""
    result = rcp_module.parse_rcp_xml(
        """
        <rcp><result><len>8</len><str>85 00 04 01 40 01 00 02</str></result></rcp>
        """,
        0x09A5,
        rcp_module.RcpDataType.OCTETS,
        "WRITE",
        1,
    )

    assert result.value == "85 00 04 01 40 01 00 02"
    assert result.string == "85 00 04 01 40 01 00 02"
