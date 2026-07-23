# Bosch Video for Home Assistant

Custom Home Assistant integration for Bosch IP cameras, initially developed and
tested with the FLEXIDOME IP 3000i IR.

The integration uses:

- ONVIF for discovery, media profiles, snapshots, imaging settings and I/O;
- ONVIF PullPoint for motion, tamper/image-quality and digital I/O events;
- RTSP for live video through Home Assistant's `stream` integration;
- Bosch RCP over HTTP Digest for features not exposed by ONVIF;
- BICOM over RCP for model-specific lens, day/night and IR controls.

The implementation is intentionally local-only. It does not use a Bosch cloud
service and the repository contains no camera address, credential, serial
number, MAC address or Home Assistant deployment data.

## Current state

This repository is under active development. Version 0.3 provides:

- a UI config flow with Bosch-compatible ONVIF authentication;
- H.264 camera profiles, snapshots and Home Assistant stream sources;
- brightness, contrast and color-saturation controls;
- relay output control;
- capability-probed day/night and IR controls over Bosch BICOM;
- capability-constrained audio codec, bitrate and sample-rate controls;
- a physical audio output level control using the camera-advertised range;
- ONVIF PullPoint binary sensors for motion, global scene change, image too
  bright/dark, digital input and relay state;
- automatic PullPoint renewal, cleanup and reconnection;
- read-only active video-analytics mode/type sensors;
- disabled-by-default recording and recording-job diagnostic counters.

The integration deliberately attempts PullPoint even when a Bosch camera
advertises `WSPullPointSupport = false`. This model reports that capability
incorrectly while accepting subscriptions.

Recording and replay services are capability-probed. Cameras with no ONVIF
recording objects do not receive playback controls; Frigate remains the
recommended recorder in that case. Video-analytics mode is currently read-only
because this firmware does not advertise the allowed SOAP values needed for
safe writes.

See the full reverse-engineered protocol description in
[`docs/BOSCH_FLEXIDOME_IP_3000I_PROTOCOL_SPEC.md`](docs/BOSCH_FLEXIDOME_IP_3000I_PROTOCOL_SPEC.md).

## Development installation

1. Copy `custom_components/bosch_video` into the Home Assistant
   `<config>/custom_components` directory.
2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration**.
4. Search for **Bosch Video** and enter the camera host, ONVIF port and a Bosch
   account with the required privileges.

The event sensors appear dynamically after the first synchronized PullPoint
response. They can be used directly as Home Assistant automation triggers. For
AI object detection, keep Frigate as the source of person/vehicle events and use
the camera's native motion and tamper sensors as complementary signals.

For the tested firmware, ONVIF uses WS-Security `UsernameToken` with
`PasswordDigest`. The integration's ONVIF dependency handles this
automatically.

## Security

- Never commit `env.txt`, `.env`, `secrets.yaml`, packet captures or diagnostics
  copied directly from a real installation.
- Diagnostics must redact host names, credentials, stream/snapshot URIs, serial
  numbers and MAC addresses.
- RCP/BICOM writes are implemented only for known commands and validated value
  ranges.

## License

MIT License. See [`LICENSE`](LICENSE).
