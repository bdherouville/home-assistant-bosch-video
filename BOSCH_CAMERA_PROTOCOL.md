# Bosch FLEXIDOME IP 3000i IR — protocol notes

> Une spécification complète destinée à la conception d'une intégration Home
> Assistant est disponible dans
> [`docs/BOSCH_FLEXIDOME_IP_3000I_PROTOCOL_SPEC.md`](docs/BOSCH_FLEXIDOME_IP_3000I_PROTOCOL_SPEC.md).

Test camera: `CAMERA_TEST_HOST`
Production/Home Assistant camera: `CAMERA_PRODUCTION_HOST` (do not modify during protocol research)

## Confirmed on the test camera

- Model: FLEXIDOME IP 3000i IR
- Firmware: 7.93.0024
- Open interfaces: HTTP 80, HTTPS 443, RTSP 554, RCP 1756
- Secure RTSP is enabled on port 9554
- ONVIF discovery is enabled in the web interface
- A WS-Discovery probe receives a response from the camera advertising both
  `http://camera.example.invalid/onvif/device_service` and
  `https://camera.example.invalid/onvif/device_service`
- ONVIF SOAP is therefore present behind HTTP/HTTPS rather than listed as a
  separate network service; authenticated SOAP calls still need to be made
  compatible with this firmware
- Bosch WebGUI configuration calls `rcp.xml` and uses RCP/RCP+ commands
- Privileged RCP reads require the `service` account; the `user` account returns
  HTTP 401 for those reads

## RCP HTTP gateway

Read-only request format:

```text
GET /rcp.xml?command=0xNNNN&type=TYPE&direction=READ&num=1
```

Authentication is HTTP Digest. The response is XML and contains either a result
or an RCP error. The read-only helper below loads credentials from `env.txt`:

```powershell
.\scripts\bosch-rcp-read.ps1 -CameraHost camera.example.invalid -Command 0x0c62 -Type P_OCTET
```

The helper intentionally hard-codes `direction=READ`; it cannot write camera
configuration.

### Commands verified

| Purpose | Command | Type | Result on test camera |
|---|---:|---|---|
| Network services | `0x0c62` | `P_OCTET` | Read succeeds |
| Audio capability flags | `0x09bf` | `T_DWORD` | `3`: line input + line output |
| Audio enabled | `0x000c` | `F_FLAG` | `0`: disabled |
| Selected audio input | `0x09b8` | `T_DWORD` | `0` |
| Alarm input capabilities | `0x0c6a` | `P_OCTET` | One physical input reported |
| Virtual alarms | `0x0aed` | `T_DWORD` | 16 supported by firmware |
| Privacy mask options | `0x0bd7` | `P_OCTET` | Eight masks reported |

## Protocol layers

1. ONVIF should be the preferred Home Assistant control/event layer once its
   unresponsive service is understood.
2. RTSP/go2rtc remains the video and audio transport for Frigate.
3. Frigate MQTT remains the AI detection/event transport.
4. RCP over HTTP is suitable for Bosch-specific reads and controlled writes that
   ONVIF does not expose.
5. Native RCP+ on TCP 1756 and BICOM are advanced fallbacks.

## ONVIF authentication verified

The test camera accepts ONVIF requests on:

```text
http://camera.example.invalid/onvif/device_service
```

The accepted authentication form is an OASIS WS-Security `UsernameToken` in a
SOAP 1.2 header:

- user: the Bosch `service` account
- password form: `PasswordDigest`
- digest: `Base64(SHA1(nonce_bytes + created_utf8 + password_utf8))`
- nonce: 16 random bytes, Base64 encoded
- created: current UTC timestamp
- transport authentication: no HTTP Basic or HTTP Digest is required

The following variants were tested:

| Variant | Result |
|---|---|
| `service` + WS-Security `PasswordDigest` | Accepted |
| `service` + WS-Security `PasswordText` | Rejected |
| `user` + WS-Security `PasswordDigest` | Rejected: not authorized |
| `service` + incorrect password digest | Rejected: not authorized |
| HTTP Basic without WS-Security | Rejected |
| No authentication | Rejected |

An authenticated `GetServices` call advertises ten endpoints:

- Device
- Media v1
- Events
- Device I/O
- Media v2
- Analytics
- Replay
- Search
- Recording
- Imaging

The standard ONVIF client test successfully returned the camera model and
firmware, then enumerated all ten service addresses.

## Safety rules before adding writes

- Discover and validate each command on `CAMERA_TEST_HOST`.
- Read the current value, allowed range, and capability flags first.
- Change one setting at a time and verify both RCP and WebGUI state.
- Keep IP/network settings and the Alarm Task Editor out of automated tests.
- Do not apply a command to `CAMERA_PRODUCTION_HOST` until it has a documented rollback.
