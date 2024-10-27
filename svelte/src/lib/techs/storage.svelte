<script type="typescript">

import {onMount} from 'svelte';
import { ListGroup, ListGroupItem, Button, Card, CardHeader, CardTitle, CardSubtitle, CardBody, Input, Spinner } from '@sveltestrap/sveltestrap';

import FetchError from '../fetch_error.svelte';
import {post} from '$lib/api.ts';

let search = "";
let searching = false;
let promise = new Promise((r,_)=>{r([])});
function search_member() {
  searching = true;
  promise = post(`/neon_lookup?search=${search}`).finally(() => searching = false);
}

</script>

<Card>
<CardHeader>
  <CardTitle>Storage Violations</CardTitle>
  <CardSubtitle>Open, close, and view storage violations</CardSubtitle>
</CardHeader>
<CardBody>
    <ListGroup>
      <ListGroupItem><a href="https://protohaven.org/wiki/shoptechs/start#%F0%9F%93%A6_storage_%F0%9F%93%A6" target="_blank">Shop Tech Central: Storage</a></ListGroupItem>
      <ListGroupItem><a href="https://protohaven.org/violations" target="_blank">Active Violations</a></ListGroupItem>
      <ListGroupItem><a href="https://airtable.com/apppMbG0r1ZrluVMv/pag7q4CIgngxTpvw5/form" target="_blank">Open a Violation</a></ListGroupItem>
      <ListGroupItem><a href="https://airtable.com/apppMbG0r1ZrluVMv/pagVSwa7QQ0sOOaEb/form" target="_blank">Close a Violation</a></ListGroupItem>
    </ListGroup>

    <strong>Search for member neon ID:</strong>

    <Input type="text" bind:value={search} disabled={searching}/>
    <Button on:click={search_member} disabled={searching || search === ""}>Search</Button>
    {#await promise}
      <Spinner/>Searching...
    {:then p}
    <ListGroup>
    {#each p as r}
      <ListGroupItem>{r}</ListGroupItem>
    {/each}
    </ListGroup>
    {:catch error}
      <FetchError {error}/>
    {/await}
</CardBody>
</Card>
