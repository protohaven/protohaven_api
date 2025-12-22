<script type="typescript">

import {onMount} from 'svelte';
import { Badge, Toast, Popover, ToastHeader, ToastBody, Dropdown, DropdownToggle, DropdownMenu, DropdownItem, Table, ListGroup, ListGroupItem, Button, Card, CardHeader, CardTitle, CardSubtitle, CardBody, Input, Spinner } from '@sveltestrap/sveltestrap';

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
let includes_email = false;
let subs_sorted = []
let sort_type = "name";
$: {
  if (sort_type === "name") {
    subs_sorted = [...subs].sort((a, b) => a.customer.toLowerCase().localeCompare(b.customer.toLowerCase()));
  } else if (sort_type === "plan") {
    subs_sorted = [...subs].sort((a, b) => a.plan.toLowerCase().localeCompare(b.plan.toLowerCase()));
  } else if (sort_type === "memstatus") {
    subs_sorted = [...subs].sort((a, b) => a.membership_status.toLowerCase().localeCompare(b.membership_status.toLowerCase()));
  } else if (sort_type === "startdate") {
    subs_sorted = [...subs].sort((a, b) => a.start_date.localeCompare(b.start_date));
  } else if (sort_type === "type") {
    subs_sorted = [...subs].sort((a, b) => a.storage_type.localeCompare(b.storage_type));
  } else if (sort_type === "idnum") {
    subs_sorted = [...subs].sort((a, b) => a.id.localeCompare(b.id));
  } else if (sort_type === "detail") {
    subs_sorted = [...subs].sort((a, b) => a.storage_detail.toLowerCase().localeCompare(b.storage_detail.toLowerCase()));
  }
}
function get_subs() {
  fetching = true;
  console.log("get_subs");
  subs_promise = get('/techs/storage_subscriptions').then((data) => {
    subs = [];
    includes_email = false;
    for (let d of data) {
      includes_email = includes_email || Boolean(d.email);
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

function handle_storage_type_select(evt, sub, typ){
  // Do async to allow the dropdown time to close
  setTimeout(() => {
    console.log(evt, sub);
    sub.storage_type=typ;
    subs_sorted = subs_sorted; // Trigger repaint
    update_sub_note(sub);
  }, 0);
}

let sub_note_editing = false;
function update_sub_note(sub) {
  sub.note = JSON.stringify({
    "storage_type": sub["storage_type"].trim(),
    "storage_id": sub["storage_id"].trim(),
    "storage_detail": sub["storage_detail"].trim(),
  })
  console.log(`Setting sub ${sub.id} note: ${sub.note}`);
  sub_note_editing = true;
  post(`/techs/storage_subscriptions/${sub.id}/note`, {"note": sub.note}).then((result) => {
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
                <DropdownItem on:click={() => sort_type="name" }>By Name</DropdownItem>
                <DropdownItem on:click={() => sort_type="plan" }>By Plan (subscription name in Square)</DropdownItem>
                <DropdownItem on:click={() => sort_type="memstatus" }>By Membership Status</DropdownItem>
                <DropdownItem on:click={() => sort_type="startdate" }>By Start Date</DropdownItem>
                <DropdownItem on:click={() => sort_type="type" }>By Storage Type</DropdownItem>
                <DropdownItem on:click={() => sort_type="idnum" }>By Storage ID</DropdownItem>
                <DropdownItem on:click={() => sort_type="detail" }>By Details</DropdownItem>
            </DropdownMenu>
        </Dropdown>
        <Table>
          <thead>
            <th>Name</th>
            {#if includes_email}<th>Email</th>{/if}
            <th>Plan</th>
            <th>Membership</th>
            <th>Start Date</th>
            <th>Type</th>
            <th>ID</th>
            <th>Detail</th>
          </thead>
          <tbody>
          {#each subs_sorted as sub}
            <tr>
                <td>{sub.customer}
                {#if sub.unpaid.length > 0}
                <Badge id={sub.id} color="danger">{sub.unpaid.length}</Badge>
                <Popover
                    target={sub.id}
                    placement="right"
                    title="Unpaid invoices"
                  >
                      {#each sub.unpaid as inv_id}
                      <div>
                        <a href={"https://app.squareup.com/dashboard/invoices/" + inv_id}>{inv_id}</a>
                      </div>
                      {/each}
                  </Popover>

                {/if}
                </td>
                {#if includes_email}<td>{sub.email}</td>{/if}
                <td>{sub.plan}</td>
                <td>{sub.membership_status}</td>
                <td>{sub.start_date}</td>
                <td>
                <Dropdown autoClose={true}>
                    <DropdownToggle caret>{sub.storage_type}</DropdownToggle>
                    <DropdownMenu>
                      {#each ["Cart", "Table", "Parking space", "Board/bar", "Sheet", "Locker", "Cage", "Rack", "Other", "Unknown"] as typ}
                        <DropdownItem disabled={sub_note_editing} on:click={(e) => handle_storage_type_select(e, sub, typ)}>{typ}</DropdownItem>
                      {/each}
                    </DropdownMenu>
                </Dropdown>
                </td>
                <td>
                <EditCell enabled={!sub_note_editing} on_change={() => update_sub_note(sub)} bind:value={sub.storage_id}/>
                </td>
                <td>
                <EditCell  enabled={!sub_note_editing} on_change={() => update_sub_note(sub)} bind:value={sub.storage_detail}/>
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
<div style="height: 120px"></div>
{/if}
