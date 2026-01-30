<script type="typescript">
  import '../../app.scss';
  import { onMount } from 'svelte';
  import {get, post} from '$lib/api.ts';

  import FetchError from '$lib/fetch_error.svelte';
  import {Spinner, ListGroup, ListGroupItem, Card, CardHeader, CardBody, CardTitle } from '@sveltestrap/sveltestrap';

  export let visible;
  let promise = new Promise(()=>{});
  onMount(() => {
	  promise = get("/class_listing");
  });
</script>

{#if visible}
<Card class="my-3">
<CardHeader>
      <CardTitle>Events</CardTitle>
</CardHeader>
<CardBody>
<p>These links apply discount codes based on your membership status and type.</p>
{#await promise}
<Spinner/>Loading...
{:then p}
  <ListGroup>
  {#each p as evt}
    <ListGroupItem>
        <div>{evt.day} {evt.time} {evt.name}</div>
        <div>{evt.description.substring(0,120)}</div>
        <div><a href={`/member/goto_class?id=${evt.id}`} target="_blank">Register</a></div>
    </ListGroupItem>
  {/each}
  </ListGroup>
{:catch error}
  <FetchError {error}/>
{/await}
</CardBody>
</Card>
{/if}
