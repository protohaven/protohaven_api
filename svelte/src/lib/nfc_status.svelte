<script lang="ts">
  // nfc_status.svelte — indicator showing NFC tap system health
  // Tracks three independent failure modes:
  //   1. Client WebSocket to Flask server
  //   2. Server MQTT connection to broker
  //   3. NFC device heartbeat (30s threshold)

  export let client_ws_connected: boolean = false;
  export let server_mqtt_connected: boolean = false;
  export let nfc_heartbeat_age_sec: number | null = null;

  const NFC_HEARTBEAT_TIMEOUT_SEC = 30;

  $: nfc_alive =
    nfc_heartbeat_age_sec !== null &&
    nfc_heartbeat_age_sec <= NFC_HEARTBEAT_TIMEOUT_SEC;

  $: all_ok = client_ws_connected && server_mqtt_connected && nfc_alive;

  // Inlined tooltip derivation — avoid function call so Svelte 4
  // properly tracks all reactive dependencies in $$.update.
  $: tooltip_lines = all_ok
    ? ["NFC tap system online"]
    : [
        ...(!client_ws_connected
          ? ["\u2022 Browser WebSocket disconnected from server"]
          : []),
        ...(!server_mqtt_connected
          ? ["\u2022 Server cannot connect to MQTT broker"]
          : []),
        ...(!nfc_alive
          ? nfc_heartbeat_age_sec === null
            ? ["\u2022 NFC device heartbeat never received"]
            : [
                `\u2022 NFC device heartbeat stale (${Math.round(
                  nfc_heartbeat_age_sec
                )}s ago, limit ${NFC_HEARTBEAT_TIMEOUT_SEC}s)`
              ]
          : [])
      ];
</script>

<div
  class="nfc-indicator"
  class:online={all_ok}
  class:offline={!all_ok}
  title={tooltip_lines.join("&#10;")}
>
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    class="nfc-icon"
  >
    <!-- NFC symbol: antenna + wave -->
    <path d="M6 8.32a7.43 7.43 0 0 1 0 7.36" />
    <path d="M9.46 5.11a9.53 9.53 0 0 1 0 13.78" />
    <path d="M12.91 1.89a12.64 12.64 0 0 1 0 20.22" />
    <rect x="4" y="2" width="16" height="20" rx="2" ry="2" />
    <line x1="8" y1="2" x2="8" y2="22" />
  </svg>
  <span class="status-dot" class:online={all_ok} class:offline={!all_ok} />
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
