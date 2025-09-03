<script type="typescript">

import {onMount} from 'svelte';
import { Dropdown, DropdownToggle, DropdownMenu, DropdownItem, Table, ListGroup, ListGroupItem, Button, Card, CardHeader, CardTitle, CardSubtitle, CardBody, Input, Spinner } from '@sveltestrap/sveltestrap';

import FetchError from '../fetch_error.svelte';
import {get} from '$lib/api.ts';
import EditCell from './editable_td.svelte'

export let visible;
let search = "";
let searching = false;
let promise = new Promise((r,_)=>{r([])});
function search_member() {
  searching = true;
  promise = post(`/neon_lookup?search=${search}`).finally(() => searching = false);
}

let fetching = false;
let subs_promise = new Promise((r,_)=>{r([])});
let subs = [];
let subs_sorted = []
let sort_type = "member";
$: {
  if (sort_type === "member") {
    subs_sorted = [...subs].sort((a, b) => a.customer.toLowerCase().localeCompare(b.customer.toLowerCase()));
  } else if (sort_type === "storage") {
    subs_sorted = [...subs].sort((a, b) => a.plan.toLowerCase().localeCompare(b.plan.toLowerCase()));
  } else if (sort_type === "note") {
    subs_sorted = [...subs].sort((a, b) => a.note.toLowerCase().localeCompare(b.note.toLowerCase()));
  }
}
function get_subs() {
  fetching = true;
  subs_promise = get('/techs/storage_subscriptions').then((data) => {
    subs = [...data];
  }).finally(() => fetching = false);
}
onMount(get_subs);

sub_note_editing = false;
function set_sub_note(sub_id, note) {
  sub_note_editing = true;
  post(`/techs/storage_subscriptions/${sub_id}/note`, data={note}).then((result) => {
    console.log(result);
    sub_note_editing = false;
    get_subs();
  });
}

</script>

{#if visible}
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

    <Card class="my-3">
    {#if sub_note_editing}
      <Spinner/>
    {/if}
    {#await subs_promise}
      <Spinner/> Loading subscription...
    {:then p}
        <Dropdown>
            <DropdownToggle color="light" caret>
                Sort
            </DropdownToggle>
            <DropdownMenu>
                <DropdownItem on:click={() => sort_type="member" }>By Name</DropdownItem>
                <DropdownItem on:click={() => sort_type="storage" }>By Storage Type</DropdownItem>
                <DropdownItem on:click={() => sort_type="note" }>By Note</DropdownItem>
            </DropdownMenu>
        </Dropdown>
        <Table>
          <thead>
            <th>Name</th>
            <th>Storage</th>
            <th>Start Date</th>
            <th>Note</th>
          </thead>
          <tbody>
          {#each subs_sorted as sub}
            <tr>
                <td>{sub.plan}</td>
                <td>{sub.customer}</td>
                <td>{sub.start_date}</td>
                <EditCell title="Note" enabled={true} on_change={() => set_sub_note(sub.id, sub.note)} bind:value={sub.note}/>
            </tr>
          {/each}
        </tbody>
      </Table>
    {:catch error}
      <FetchError {error}/>
    {/await}
    </Card>

    <strong>Search for member neon ID:</strong>

    <Input type="text" bind:value={search} disabled={searching}/>
    <Button on:click={search_member} disabled={searching || search === ""}>Search</Button>
    {#await promise}
      <Spinner/> Searching...
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
{/if}
