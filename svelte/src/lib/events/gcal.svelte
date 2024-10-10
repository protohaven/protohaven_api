<script lang="ts">
  import { onMount } from 'svelte';
  import { Card, CardBody, CardHeader, CardTitle, Spinner, ListGroup, ListGroupItem } from '@sveltestrap/sveltestrap';
  import { get } from '$lib/api';
import FetchError from '../fetch_error.svelte';

  let promise = new Promise(()=>{});
  onMount(() => {
    promise = get("/events/shop");
  });
</script>

<Card>
  <CardHeader>
    <CardTitle>Upcoming Shop Events</CardTitle>
  </CardHeader>
  <CardBody>
  {#await promise}
      <Spinner/>
  {:then p}
    <ListGroup>
    {#each p as evt }
    <ListGroupItem>{new Date(evt.start).toLocaleString()}: {evt.name}</ListGroupItem>
    {/each}
    </ListGroup>
  {:catch error}
    <FetchError {error}/>
  {/await}
  </CardBody>
</Card>
