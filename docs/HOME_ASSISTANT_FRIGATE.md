# Home Assistant, Frigate and alarm-panel usage

This guide intentionally contains placeholders only. Never commit a camera
address, RTSP credential, Telegram token, chat ID, Frigate credential, or Home
Assistant diagnostic archive.

## Responsibilities

Use each component for the job it handles best:

- Bosch Video: native camera streams, settings, I/O and ONVIF events;
- Frigate: person/object detection, snapshots, clips and retention;
- a Home Assistant alarm control panel: the authoritative armed/disarmed state;
- Telegram bot: commands and delivery of alerts.

Do not infer the alarm state from a switch or a Telegram message. Automations
must read an actual `alarm_control_panel` entity and require the exact
`armed_away` state.

## Multiple cameras

Add each physical camera as a separate Bosch Video config entry. The
integration uses the camera's stable ONVIF identity, so identical profile,
input, relay and event tokens on two cameras cannot collide.

Use **Reconfigure** on the integration entry when Home Assistant must connect
to the same camera through a different host name or port. Reconfigure changes
only Home Assistant's connection data; it does not change the camera's network
configuration. The flow aborts if the new address belongs to another physical
camera.

Keep the Frigate camera name stable after automations are deployed. For more
than one Frigate server, configure a distinct MQTT `client_id` and
`topic_prefix` for each server and include the client ID in notification API
URLs.

## Snapshot followed by clip

The package example in
[`examples/frigate_alarm_telegram.yaml`](../examples/frigate_alarm_telegram.yaml)
contains two automations:

1. the first available person snapshot is sent while the panel is
   `armed_away`;
2. the completed clip is sent when Frigate publishes the end of the same kind
   of event and reports `has_clip`.

Replace:

- `alarm_control_panel.replace_with_alarm_panel`;
- `notify.replace_with_telegram_notifier`;
- `replace_with_frigate_camera_name`;
- `http://homeassistant.local:8123` if that name is not reachable from Home
  Assistant itself.

The Telegram bot integration downloads the internal Frigate notification URL
and uploads the resulting media to Telegram. No camera credential belongs in
the automation.

Before enabling the automations:

1. verify MQTT and the official Frigate integration are connected;
2. confirm Frigate publishes `frigate/events`;
3. test `telegram_bot.send_photo` and `telegram_bot.send_video` from Developer
   Tools using the intended notify entity;
4. arm the panel in a controlled test;
5. confirm the snapshot arrives before the completed clip;
6. disarm and confirm no further test event produces an alert.

Current references:

- [Frigate Home Assistant integration and notification API](https://docs.frigate.video/integrations/home-assistant/)
- [Frigate MQTT event schema](https://docs.frigate.video/integrations/mqtt/)
- [Home Assistant Telegram bot: send photo](https://www.home-assistant.io/actions/telegram_bot.send_photo/)
- [Home Assistant Telegram bot: send video](https://www.home-assistant.io/actions/telegram_bot.send_video/)
