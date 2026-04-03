<script lang="ts">
  import { onMount } from 'svelte';
  import { Card, CardBody, CardHeader, CardTitle, Spinner, ListGroup, ListGroupItem, Badge, Tooltip } from '@sveltestrap/sveltestrap';
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

  function uniqueStarts(reservations) {
    const uniques = {};
    for (let r of reservations) {
      uniques[r.start] = r.ts;
    }
    const sorted = Array.from(Object.entries(uniques)).sort((a,b) => {
      return b[1] < a[1] ?  1
          :  b[1] > a[1] ? -1
          :  0;
    });
    return sorted.map((a)=>a[0]).join(', ');
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
    <ListGroup>
      {#each Object.entries(groupReservations(p)) as [owner, areas]}
        <ListGroupItem>
          <strong>{owner}</strong>
          <div style="margin-top: 0.5rem;">
            {#each Object.entries(areas) as [area, areaReservations]}
              <Tooltip
                target={"res-" + areaReservations[0].id}
                placement="top"
                style="max-width: 300px;"
              >
                <div>
                  <ul style="margin-bottom: 0; padding-left: 1rem;">
                    {#each areaReservations as r}
                      <li>
                          <div>{r.resource}</div>
                          <div>({r.start} - {r.end})</div>

                      </li>
                    {/each}
                  </ul>
                </div>
              </Tooltip>
              <Badge
                id={"res-" + areaReservations[0].id}
                color="primary"
                pill
                style="margin-right: 0.5rem; margin-bottom: 0.5rem; cursor: pointer;"
              >
                {area} ({areaReservations.length} resources, {uniqueStarts(areaReservations)})
              </Badge>
            {/each}
          </div>
        </ListGroupItem>
      {/each}
    </ListGroup>
  {:catch error}
    <FetchError {error}/>
  {/await}
  </CardBody>
</Card>
