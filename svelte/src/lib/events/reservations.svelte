<script lang="ts">
  import { onMount } from 'svelte';
  import { Card, CardBody, CardHeader, CardTitle, Spinner, ListGroup, ListGroupItem } from '@sveltestrap/sveltestrap';
  import { get } from '$lib/api';
import FetchError from '../fetch_error.svelte';

  let promise = new Promise(()=>{});
  onMount(() => {
    promise = get("/events/reservations");
  });
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
    {#each p as r }
    <ListGroupItem>
      {r.resource}: {r.start} - {r.end} by {r.name}
    </ListGroupItem>
    {/each}
    </ListGroup>
  {:catch error}
    <FetchError {error}/>
  {/await}
  </CardBody>
</Card>
