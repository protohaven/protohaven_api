<script type="typescript">
  import '../../app.scss';
  import { onMount } from 'svelte';
  import {get, post} from '$lib/api.ts';

  import FetchError from '$lib/fetch_error.svelte';
  import {Spinner, ListGroup, ListGroupItem } from '@sveltestrap/sveltestrap';

  let promise = new Promise(()=>{});
  onMount(() => {
	  promise = get("/class_listing");
  });
</script>

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
