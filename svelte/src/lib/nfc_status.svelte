<script type="typescript" lang="ts">
  import { Tooltip, Icon } from '@sveltestrap/sveltestrap';
  // nfc_status.svelte — indicator showing NFC tap system health
  // Tracks three independent failure modes:
  //   1. Client WebSocket to Flask server
  //   2. Server MQTT connection to broker
  //   3. NFC device heartbeat (30s threshold)

  export let client_ws_connected: boolean = false;
  export let server_mqtt_connected: boolean = false;
  export let nfc_heartbeat_age_sec: number | null = null;

  const NFC_HEARTBEAT_TIMEOUT_SEC = 60;

  $: nfc_alive =
    nfc_heartbeat_age_sec !== null &&
    nfc_heartbeat_age_sec <= NFC_HEARTBEAT_TIMEOUT_SEC;

  $: all_ok = client_ws_connected && server_mqtt_connected && nfc_alive;

  // Inlined tooltip derivation — avoid function call so Svelte 4
  // properly tracks all reactive dependencies in $$.update.
  $: tooltip_lines = all_ok
    ? [`NFC tap system online; last contact ${Math.round(nfc_heartbeat_age_sec)}s`]
    : [
        ...(!client_ws_connected
          ? ["Browser WebSocket disconnected from server"]
          : []),
        ...(!server_mqtt_connected
          ? ["Server cannot connect to MQTT broker"]
          : []),
        ...(!nfc_alive
          ? nfc_heartbeat_age_sec === null
            ? ["NFC device heartbeat never received"]
            : [
                `NFC device heartbeat stale (${Math.round(
                  nfc_heartbeat_age_sec
                )}s ago, limit ${NFC_HEARTBEAT_TIMEOUT_SEC}s)`
              ]
          : [])
      ];
</script>

<Tooltip target="nfc-indicator">
  {#each tooltip_lines as tl}
  <p>{tl}</p>
  {/each}
</Tooltip>
<div
  class="nfc-indicator"
  id="nfc-indicator"
  class:online={all_ok}
  class:offline={!all_ok}
>
  <Icon name="wifi" />Tap Sign In {all_ok ? "Online" : "Offline"}
</div>

<style>
  .nfc-indicator {
    position: fixed;
    bottom: 16px;
    right: 16px;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.92);
    box-shadow: 0 1px 6px rgba(0, 0, 0, 0.15);
    z-index: 9998;
    cursor: default;
    transition: background 0.3s;
  }

  .nfc-indicator.offline {
    background: rgba(255, 240, 240, 0.95);
  }

  .nfc-icon {
    width: 22px;
    height: 22px;
    opacity: 0.7;
  }

  .offline .nfc-icon {
    color: #c44;
  }

  .online .nfc-icon {
    color: #494;
  }

  .status-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .status-dot.online {
    background: #4a4;
    box-shadow: 0 0 6px rgba(68, 170, 68, 0.5);
  }

  .status-dot.offline {
    background: #c44;
    box-shadow: 0 0 6px rgba(204, 68, 68, 0.4);
  }
</style>
