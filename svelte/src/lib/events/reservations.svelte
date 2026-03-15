<script lang="ts">
  import { onMount } from 'svelte';
  import { Card, CardBody, CardHeader, CardTitle, Spinner, ListGroup, ListGroupItem } from '@sveltestrap/sveltestrap';
  import { get } from '$lib/api';
import FetchError from '../fetch_error.svelte';

  let promise = new Promise(()=>{});
  onMount(() => {
    promise = get("/events/reservations");
  });

  // Group reservations by owner and area
  function groupReservations(reservations: any[]) {
    const grouped: Record<string, Record<string, any[]>> = {};

    for (const reservation of reservations) {
      const owner = reservation.name;
      const area = reservation.area;

      if (!grouped[owner]) {
        grouped[owner] = {};
      }

      if (!grouped[owner][area]) {
        grouped[owner][area] = [];
      }

      grouped[owner][area].push(reservation);
    }

    return grouped;
  }
</script>

<Card>
  <CardHeader>
    <CardTitle>Today's Reservations</CardTitle>
  </CardHeader>
  <CardBody>
  {#await promise}
      <Spinner/>
  {:then p}
    {#const grouped = groupReservations(p)}
    <ListGroup>
      {#each Object.entries(grouped) as [owner, areas]}
        <ListGroupItem>
          <strong>{owner}</strong>
          {#each Object.entries(areas) as [area, areaReservations]}
            <div style="margin-left: 1rem; margin-top: 0.5rem;">
              <em>{area}:</em>
              <ul style="margin-bottom: 0;">
                {#each areaReservations as r}
                  <li>{r.resource} ({r.start} - {r.end})</li>
                {/each}
              </ul>
            </div>
          {/each}
        </ListGroupItem>
      {/each}
    </ListGroup>
  {:catch error}
    <FetchError {error}/>
  {/await}
  </CardBody>
</Card>
