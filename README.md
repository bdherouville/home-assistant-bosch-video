# Bosch Video for Home Assistant

Custom Home Assistant integration for Bosch IP cameras, initially developed and
tested with the FLEXIDOME IP 3000i IR.

The integration uses:

- ONVIF for discovery, media profiles, snapshots, imaging settings and I/O;
- RTSP for live video through Home Assistant's `stream` integration;
- Bosch RCP over HTTP Digest for features not exposed by ONVIF;
- BICOM over RCP for model-specific lens, day/night and IR controls.

The implementation is intentionally local-only. It does not use a Bosch cloud
service and the repository contains no camera address, credential, serial
number, MAC address or Home Assistant deployment data.

## Current state

This repository is under active development. The first usable milestone
provides a UI config flow, H.264 camera profiles, snapshots, stream sources,
device metadata, imaging controls and relay control. Bosch-specific RCP/BICOM
features are being added behind capability checks.

See the full reverse-engineered protocol description in
[`docs/BOSCH_FLEXIDOME_IP_3000I_PROTOCOL_SPEC.md`](docs/BOSCH_FLEXIDOME_IP_3000I_PROTOCOL_SPEC.md).

## Development installation

1. Copy `custom_components/bosch_video` into the Home Assistant
   `<config>/custom_components` directory.
2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration**.
4. Search for **Bosch Video** and enter the camera host, ONVIF port and a Bosch
   account with the required privileges.

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
