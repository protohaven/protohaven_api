<script type="typescript">

import {onMount} from 'svelte';
import { Toast, ToastHeader, ToastBody, Dropdown, DropdownToggle, DropdownMenu, DropdownItem, Table, ListGroup, ListGroupItem, Button, Card, CardHeader, CardTitle, CardSubtitle, CardBody, Input, Spinner } from '@sveltestrap/sveltestrap';

import FetchError from '../fetch_error.svelte';
import {get, post} from '$lib/api.ts';
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
let toast_msg = null;
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
  console.log("get_subs");
  subs_promise = get('/techs/storage_subscriptions').then((data) => {
    subs = [];
    for (let d of data) {
      let parsed = {};
      try {
        parsed = JSON.parse(d["note"]);
        console.log("Parsed", parsed);
      } catch (e) {
        console.warn("Failed parsing note", d, e);
      }
      d["storage_type"] = parsed["storage_type"] || "Unknown";
      d["storage_id"] = parsed["storage_id"] || "Unknown";
      d["storage_detail"] = parsed["storage_detail"] || d["note"] || "Unknown";
    }
    subs = [...data];
    console.log(subs)
  }).finally(() => fetching = false);
}
onMount(get_subs);

let sub_note_editing = false;
function set_sub_note(sub_id, sub) {
  sub.note = JSON.stringify({
    "storage_type": sub["storage_type"],
    "storage_id": sub["storage_id"],
    "storage_detail": sub["storage_detail"],
  })
  console.log("Setting sub note:", sub.note);
  sub_note_editing = true;
  post(`/techs/storage_subscriptions/${sub_id}/note`, {"note": sub.note}).then((result) => {
    console.log(result);
    let msg = `${sub.customer} subscription notes updated`;
    toast_msg = {'color': 'success', msg, 'title': 'Edit Success'};
    //get_subs();
  }).catch((err) => {
      console.error(err);
      toast_msg = {'color': 'danger', 'msg': 'See console for details', 'title': 'Error updating subscription notes'};
    }).finally(() => sub_note_editing = false);
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

<Card class="my-3">
<CardHeader>
<CardTitle>Storage Subscriptions</CardTitle>
<CardSubtitle>View active subscriptions and add details</CardSubtitle>
</CardHeader>
<CardBody>
    {#if sub_note_editing}
      <Spinner/>
    {/if}
    {#await subs_promise}
      <Spinner/> Loading subscription...
    {:then p}
        <Toast class="me-1" style="z-index: 10000; position:fixed; bottom: 2vh; right: 2vh;" autohide isOpen={toast_msg} on:close={() => (toast_msg = null)}>
          <ToastHeader icon={toast_msg.color}>{toast_msg.title}</ToastHeader>
          <ToastBody>{toast_msg.msg}</ToastBody>
        </Toast>
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
            <th>Type</th>
            <th>ID</th>
            <th>Detail</th>
          </thead>
          <tbody>
          {#each subs_sorted as sub}
            <tr>
                <td>{sub.plan}</td>
                <td>{sub.customer}</td>
                <td>{sub.start_date}</td>
                <td>
                <Dropdown>
                    <DropdownToggle caret>{sub.storage_type}</DropdownToggle>
                    <DropdownMenu>
                      {#each ["Cart", "Table", "Parking space", "Board/bar", "Sheet", "Locker", "Cage", "Rack", "Other", "Unknown"] as typ}
                        <DropdownItem disabled={sub_note_editing} on:click={() => { sub.storage_type=typ; set_sub_note(sub.id, sub); }}>{typ}</DropdownItem>
                      {/each}
                    </DropdownMenu>
                </Dropdown>
                </td>
                <td>
                <EditCell enabled={!sub_note_editing} on_change={() => set_sub_note(sub.id, sub)} bind:value={sub.storage_id}/>
                </td>
                <td>
                <EditCell  enabled={!sub_note_editing} on_change={() => set_sub_note(sub.id, sub)} bind:value={sub.storage_detail}/>
                </td>
            </tr>
          {/each}
        </tbody>
      </Table>
    {:catch error}
      <FetchError {error}/>
    {/await}
</CardBody>
</Card>
{/if}
