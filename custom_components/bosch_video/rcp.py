"""Bosch RCP XML transport with HTTP Digest authentication.

This module deliberately contains no Home Assistant imports so it can later be
extracted into a standalone Python package.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.parse import urlencode, urlsplit

from aiohttp import ClientResponse, ClientSession


class RcpDataType(StrEnum):
    """Known RCP XML value types."""

    FLAG = "F_FLAG"
    OCTET = "T_OCTET"
    WORD = "T_WORD"
    DWORD = "T_DWORD"
    STRING = "P_STRING"
    UNICODE = "P_UNICODE"
    OCTETS = "P_OCTET"


class RcpError(Exception):
    """Base RCP protocol error."""


class RcpAuthenticationError(RcpError):
    """HTTP Digest authentication failed."""


class RcpCommandError(RcpError):
    """The camera returned an RCP error code."""

    def __init__(self, code: str) -> None:
        """Initialize the error."""
        self.code = code
        super().__init__(f"The camera returned RCP error {code}")


@dataclass(slots=True, frozen=True)
class RcpResponse:
    """Decoded RCP XML response."""

    command: int
    data_type: RcpDataType
    direction: str
    num: int
    auth_level: int | None
    protocol: str | None
    value: str
    hexadecimal: str | None = None
    decimal: int | None = None
    string: str | None = None


_DIGEST_PAIR = re.compile(
    r"([A-Za-z][A-Za-z0-9_-]*)\s*=\s*(?:\"((?:[^\"\\]|\\.)*)\"|([^,\s]+))"
)


def parse_digest_challenge(header: str) -> dict[str, str]:
    """Parse one RFC 7616 Digest challenge."""
    if not header.lower().startswith("digest "):
        raise RcpAuthenticationError("The camera did not offer HTTP Digest")
    values: dict[str, str] = {}
    for match in _DIGEST_PAIR.finditer(header[7:]):
        key = match.group(1).lower()
        value = match.group(2) if match.group(2) is not None else match.group(3)
        values[key] = value.replace(r"\"", '"')
    if not values.get("realm") or not values.get("nonce"):
        raise RcpAuthenticationError("The Digest challenge is incomplete")
    return values


def _digest_hash(algorithm: str, value: str) -> str:
    """Hash a Digest field using a supported RFC 7616 algorithm."""
    normalized = algorithm.upper().removesuffix("-SESS")
    algorithm_names = {
        "MD5": "md5",
        "SHA-256": "sha256",
        "SHA-512-256": "sha512_256",
    }
    try:
        algorithm_name = algorithm_names[normalized]
        hasher = hashlib.new(algorithm_name, usedforsecurity=False)
    except (KeyError, ValueError) as err:
        raise RcpAuthenticationError(
            f"Unsupported Digest algorithm: {algorithm}"
        ) from err
    hasher.update(value.encode("utf-8"))
    return hasher.hexdigest()


def build_digest_authorization(
    *,
    challenge: dict[str, str],
    username: str,
    password: str,
    method: str,
    request_target: str,
    nonce_count: int,
    cnonce: str,
) -> str:
    """Build a Digest Authorization header."""
    realm = challenge["realm"]
    nonce = challenge["nonce"]
    algorithm = challenge.get("algorithm", "MD5")
    qop_options = {
        item.strip().lower()
        for item in challenge.get("qop", "").split(",")
        if item.strip()
    }
    if qop_options and "auth" not in qop_options:
        raise RcpAuthenticationError("The camera does not offer Digest qop=auth")

    ha1 = _digest_hash(algorithm, f"{username}:{realm}:{password}")
    if algorithm.upper().endswith("-SESS"):
        ha1 = _digest_hash(algorithm, f"{ha1}:{nonce}:{cnonce}")
    ha2 = _digest_hash(algorithm, f"{method}:{request_target}")
    nc = f"{nonce_count:08x}"
    if qop_options:
        response = _digest_hash(
            algorithm,
            f"{ha1}:{nonce}:{nc}:{cnonce}:auth:{ha2}",
        )
    else:
        response = _digest_hash(algorithm, f"{ha1}:{nonce}:{ha2}")

    fields = [
        f'username="{username}"',
        f'realm="{realm}"',
        f'nonce="{nonce}"',
        f'uri="{request_target}"',
        f'response="{response}"',
        f"algorithm={algorithm}",
    ]
    if opaque := challenge.get("opaque"):
        fields.append(f'opaque="{opaque}"')
    if qop_options:
        fields.extend(("qop=auth", f"nc={nc}", f'cnonce="{cnonce}"'))
    return "Digest " + ", ".join(fields)


class BoschRcpClient:
    """Call the Bosch `/rcp.xml` HTTP gateway."""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        username: str,
        password: str,
        *,
        port: int = 80,
        use_https: bool = False,
        verify_ssl: bool = True,
    ) -> None:
        """Initialize the RCP transport."""
        scheme = "https" if use_https else "http"
        self._base_url = f"{scheme}://{host}:{port}/rcp.xml"
        self._session = session
        self._username = username
        self._password = password
        self._ssl: bool | None = None if verify_ssl else False
        self._challenge: dict[str, str] | None = None
        self._nonce_count = 0

    async def async_read(
        self,
        command: int,
        data_type: RcpDataType,
        *,
        num: int = 1,
    ) -> RcpResponse:
        """Read one RCP value."""
        return await self._async_request(command, data_type, "READ", num=num)

    async def async_write(
        self,
        command: int,
        data_type: RcpDataType,
        payload: str,
        *,
        num: int = 1,
    ) -> RcpResponse:
        """Write one RCP value.

        Callers must apply a command-specific allowlist and range validation.
        """
        return await self._async_request(
            command,
            data_type,
            "WRITE",
            num=num,
            payload=payload,
        )

    async def _async_request(
        self,
        command: int,
        data_type: RcpDataType,
        direction: str,
        *,
        num: int,
        payload: str | None = None,
    ) -> RcpResponse:
        """Perform an authenticated RCP request."""
        if not 0 <= command <= 0xFFFF:
            raise ValueError("RCP command must fit in 16 bits")
        if not 0 <= num <= 255:
            raise ValueError("RCP num must fit in 8 bits")
        params: dict[str, Any] = {
            "command": f"0x{command:04x}",
            "type": data_type.value,
            "direction": direction,
            "num": num,
        }
        if payload is not None:
            params["payload"] = payload
        url = f"{self._base_url}?{urlencode(params)}"

        response = await self._send(url)
        if response.status == 401:
            challenge_header = response.headers.get("WWW-Authenticate", "")
            await response.read()
            self._challenge = parse_digest_challenge(challenge_header)
            response = await self._send(url, authenticated=True)
        if response.status in (401, 403):
            await response.read()
            raise RcpAuthenticationError("The camera rejected the credentials")
        response.raise_for_status()
        body = await response.text()
        return parse_rcp_xml(body, command, data_type, direction, num)

    async def _send(self, url: str, *, authenticated: bool = False) -> ClientResponse:
        """Send one request, optionally using the cached Digest challenge."""
        headers: dict[str, str] = {}
        if authenticated or self._challenge is not None:
            if self._challenge is None:
                raise RcpAuthenticationError("No Digest challenge is available")
            self._nonce_count += 1
            parsed = urlsplit(url)
            target = parsed.path + (f"?{parsed.query}" if parsed.query else "")
            headers["Authorization"] = build_digest_authorization(
                challenge=self._challenge,
                username=self._username,
                password=self._password,
                method="GET",
                request_target=target,
                nonce_count=self._nonce_count,
                cnonce=secrets.token_hex(16),
            )
        return await self._session.get(
            url,
            headers=headers,
            ssl=self._ssl,
            timeout=10,
        )


def parse_rcp_xml(
    body: str,
    command: int,
    data_type: RcpDataType,
    direction: str,
    num: int,
) -> RcpResponse:
    """Decode an RCP XML response."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError as err:
        raise RcpError("The camera returned invalid RCP XML") from err
    result = root.find("result")
    if result is None:
        raise RcpError("The RCP response has no result element")
    if (error := result.find("err")) is not None:
        raise RcpCommandError("".join(error.itertext()).strip())
    hexadecimal = result.findtext("hex")
    decimal_text = result.findtext("dec")
    string = result.findtext("str")
    decimal = (
        int(decimal_text)
        if decimal_text and decimal_text.lstrip("-").isdigit()
        else None
    )
    if (
        data_type
        in {
            RcpDataType.FLAG,
            RcpDataType.OCTET,
            RcpDataType.WORD,
            RcpDataType.DWORD,
        }
        and decimal is not None
    ):
        value = str(decimal)
    elif (
        data_type
        in {
            RcpDataType.OCTETS,
            RcpDataType.STRING,
            RcpDataType.UNICODE,
        }
        and string is not None
    ):
        value = string.strip()
    elif data_type is RcpDataType.OCTETS and hexadecimal:
        value = hexadecimal.strip()
    else:
        value = "".join(result.itertext()).strip()
    auth_text = root.findtext("auth")
    return RcpResponse(
        command=command,
        data_type=data_type,
        direction=direction,
        num=num,
        auth_level=int(auth_text) if auth_text and auth_text.isdigit() else None,
        protocol=root.findtext("protocol"),
        value=value,
        hexadecimal=hexadecimal.strip() if hexadecimal else None,
        decimal=decimal,
        string=string.strip() if string else None,
    )
