<script type="typescript">
  import { onMount, onDestroy } from 'svelte';
  import { get } from '$lib/api.ts';
  import { Icon, Tooltip, Badge, Spinner } from '@sveltestrap/sveltestrap';

  export let visible = true;

  let doorStates: Array<{
    name: string;
    mac: string;
    is_online: boolean;
    open_close_state: boolean;
  }> = [];
  let lastUpdated: string = '';
  let loading = false;
  let error: string | null = null;
  let refreshInterval: number | null = null;

  // Function to fetch door lock status
  async function fetchDoorLocks() {
    if (loading) return;
    loading = true;
    error = null;

    try {
      const data = await get('/techs/door_locks');
      doorStates = data.doors || [];
      lastUpdated = data.timestamp || '';
    } catch (err) {
      console.error('Failed to fetch door locks:', err);
      error = 'Failed to load door status';
    } finally {
      loading = false;
    }
  }

  // Format timestamp for display
  function formatTime(timestamp: string): string {
    if (!timestamp) return 'Never';
    try {
      const date = new Date(timestamp);
      return date.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
      });
    } catch {
      return 'Invalid time';
    }
  }

  // Get door icon based on state
  function getDoorIcon(door: any): string {
    if (!door.is_online) return 'question-circle';
    return door.open_close_state ? 'door-open' : 'door-closed';
  }

  // Get door color based on state
  function getDoorColor(door: any): string {
    if (!door.is_online) return 'secondary';
    return door.open_close_state ? 'danger' : 'success';
  }

  // Get door tooltip text
  function getDoorTooltip(door: any): string {
    if (!door.is_online) return `${door.name}: Offline`;
    return `${door.name}: ${door.open_close_state ? 'OPEN' : 'CLOSED'}`;
  }

  // Count open doors
  $: openDoors = doorStates.filter(d => d.is_online && d.open_close_state).length;
  $: offlineDoors = doorStates.filter(d => !d.is_online).length;

  onMount(() => {
    // Fetch immediately on mount
    fetchDoorLocks();

    // Set up auto-refresh every 5 minutes (300000 ms)
    refreshInterval = window.setInterval(fetchDoorLocks, 5 * 60 * 1000);
  });

  onDestroy(() => {
    if (refreshInterval) {
      clearInterval(refreshInterval);
    }
  });
</script>

{#if visible}
  <div class="door-locks-status">
    {#if loading && doorStates.length === 0}
      <Spinner color="light" size="sm" />
    {:else if error}
      <Tooltip target="door-error" placement="bottom">
        {error}
      </Tooltip>
      <Icon name="exclamation-triangle" color="warning" id="door-error" />
    {:else}
      <div class="d-flex align-items-center gap-2">
        {#if doorStates.length === 0}
          <Tooltip target="no-doors" placement="bottom">
            No door sensors configured
            {#if lastUpdated}
              <br />
              Last updated: {formatTime(lastUpdated)}
            {/if}
          </Tooltip>
          <Icon
            name="slash-circle"
            color="secondary"
            id="no-doors"
            class="door-icon"
          />
        {:else}
          <!-- Door icons -->
          {#each doorStates as door}
            <Tooltip target={`door-${door.mac}`} placement="bottom">
              {getDoorTooltip(door)}
            </Tooltip>
            <Icon
              name={getDoorIcon(door)}
              color={getDoorColor(door)}
              id={`door-${door.mac}`}
              class="door-icon"
            />
          {/each}

          <!-- Status badge -->
          {#if openDoors > 0 || offlineDoors > 0}
            <Tooltip target="door-status-badge" placement="bottom">
              {openDoors} door{#if openDoors !== 1}s{/if} open
              {#if offlineDoors > 0}
                <br />
                {offlineDoors} door{#if offlineDoors !== 1}s{/if} offline
              {/if}
              {#if lastUpdated}
                <br />
                Last updated: {formatTime(lastUpdated)}
              {/if}
            </Tooltip>
            <Badge
              color={openDoors > 0 ? 'danger' : (offlineDoors > 0 ? 'warning' : 'success')}
              id="door-status-badge"
              class="door-badge"
            >
              {openDoors > 0 ? `${openDoors} open` : 'All closed'}
            </Badge>
          {:else}
            <Tooltip target="door-status-badge" placement="bottom">
              All doors closed
              {#if lastUpdated}
                <br />
                Last updated: {formatTime(lastUpdated)}
              {/if}
            </Tooltip>
            <Badge
              color="success"
              id="door-status-badge"
              class="door-badge"
            >
              ✓
            </Badge>
          {/if}
        {/if}

        <!-- Refresh indicator -->
        {#if loading}
          <Spinner color="light" size="sm" />
        {/if}
      </div>
    {/if}
  </div>
{/if}

<style>
  .door-locks-status {
    display: inline-block;
  }

  .door-icon {
    font-size: 1.2rem;
    cursor: help;
  }

  .door-badge {
    cursor: help;
    font-size: 0.8rem;
    padding: 0.15rem 0.4rem;
  }
</style>
