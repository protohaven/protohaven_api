<script type="typescript">
import { onMount } from 'svelte';
import { Button, Row, Tooltip, Col, Card, CardHeader, CardTitle, CardSubtitle, CardText, CardFooter, CardBody, Input, Spinner, FormGroup, Dropdown, DropdownMenu, DropdownItem, DropdownToggle, Navbar, NavbarBrand, Nav, NavItem, Alert } from '@sveltestrap/sveltestrap';
import {get, post} from '$lib/api.ts';
import FetchError from '../fetch_error.svelte';

export let eid;

export let c_init;
let meta_promise = Promise.resolve(c_init);


let attendees = [];
let neon_state = null;

function fetch_neon_state(data) {
  if (data.neon_id) {
    console.log("Fetching state for", data.neon_id);
    return get("/instructor/class/neon_state?id=" + encodeURIComponent(data.neon_id)).then((data) => {
      neon_state = data;
      return data;
    });
  }
  return null;
}

function fetch_attendees(data) {
  if (data.neon_id) {
    console.log("Fetching attendees for", data.neon_id);
    return get("/instructor/class/attendees?id=" + encodeURIComponent(data.neon_id)).then((data) => {
      attendees = data;
      return data;
    });
  }
  return [];
}
let promise = meta_promise.then(fetch_attendees);
let state_promise = meta_promise.then(fetch_neon_state);


function refresh(neon_id) {
  if (neon_id) {
    promise = get("/instructor/class/attendees?id=" + encodeURIComponent(neon_id));
  }
  return promise;
}
//onMount(refresh);

function confirm(pub) {
  meta_promise = post("/instructor/class/update", {eid, pub})
  promise = meta_promise.then(fetch_attendees);
  state_promise = meta_promise.then(fetch_neon_state);
}

function submit_log(url) {
  let attendees_for_log = [];
  for (let d of attendees) {
    attendees_for_log.push(`${d.firstName} ${d.lastName} (${d.email})`);
  }
  console.log("Attendees:", attendees_for_log);
  url = url.replace("ATTENDEE_NAMES", encodeURIComponent(attendees_for_log.join(", ")));
  console.log("Opening log url", url);
  window.open(url, "_blank");
}

function supply(ok) {
  meta_promise = post("/instructor/class/supply_req", {eid, missing: !ok})
  promise = meta_promise.then(fetch_attendees);
  state_promise = meta_promise.then(fetch_neon_state);
}

function volunteer(v) {
  meta_promise = post("/instructor/class/volunteer", {eid, volunteer: v})
  promise = meta_promise.then(fetch_attendees);
  state_promise = meta_promise.then(fetch_neon_state);
}

function cancel(neon_id) {
  meta_promise = post("/instructor/class/cancel", {neon_id});
  promise = meta_promise.then(fetch_attendees);
  state_promise = meta_promise.then(fetch_neon_state);
}
</script>

{#await meta_promise}
  <Spinner/>
{:then c}
<Card class="my-3" size={'lg'}>
<CardHeader style={(c.neon_id) ? "background-color: rgb(230, 225, 249)" : ""}>
  <CardTitle id={eid}>
    {#if c.neon_id}
      <i class="bi bi-calendar-check"></i>
    {:else}
      <a href="https://protohaven.org/wiki/instructors#scheduling" target="_blank"><i class="bi bi-question-circle"></i></a> PROPOSED:
    {/if}
    {c.name}
  </CardTitle>
  {#if !c.neon_id}
  <Tooltip target={eid} placement="right">
  	Proposed classes are not guaranteed to run; they aren't yet available for people to register in Neon. Click the ? icon for more details.
  </Tooltip>
  {/if}
</CardHeader>
<CardBody>

  {#await state_promise}
    <Spinner/>
  {:then p}
    {#if p && (!p.publishEvent || p.archived)}
      <Alert color='warning'>This class has been canceled.</Alert>
    {/if}
  {:catch error}
    Error: {error.message}
  {/await}

  {#if c.rejected}
    <Alert color="warning" class="mx-3">This card will disappear upon refreshing the page.</Alert>
  {/if}

  <CardSubtitle>Dates:</CardSubtitle>
  <CardText>
    <ul>
      {#each c.sessions as ss}
      <li>
          {new Date(ss[0]).toLocaleString()} -
          {new Date(ss[1]).toLocaleString()}</li>
      {/each}
    </ul>
  </CardText>

  {#await promise}
    <Spinner/>
  {:then p}
    <CardSubtitle>Attendees:</CardSubtitle>
    <CardText>
      {#if p.length == 0}
	None
      {:else}
      <ul class="attendees">
	{#each p as a}
	<li>
      {#if a.registrationStatus !== "SUCCEEDED" }
      <strong>{a.registrationStatus}</strong> -
      {/if}
      {a.firstName} {a.lastName} ({a.email}) registered {a.registrationDate}
  </li>
	{/each}
      </ul>
      {/if}
    </CardText>
  {:catch error}
    Error: {error.message}
  {/await}

  <CardSubtitle>Details:</CardSubtitle>
  <CardText>
  <ul>
  <li># Seats:  {c.capacity}</li>
  <li>{c.supply_state}
    {#if c.supply_state == 'Supplies Requested'}
      <strong>- remember to file <a href="https://form.asana.com/?k=syF2O04JfU-Z82q6NcEJKg&d=1199692158232291" target="_blank">purchase requests</a></strong>
    {/if}
  </li>
  <li>Instruction: {#if c.volunteer}Volunteer (no pay){:else}Paid{/if} </li>
  <li>Instructor confirmed:  {#if c.confirmed}on {new Date(c.confirmed).toLocaleString()}{:else}no{/if}</li>
  </ul>
  {#if c.clearances.length > 0}
  <div>Clearances earned:</div>
  <ul>
    {#each c.clearances as clr}
    <li>{clr}</li>
    {/each}
  </ul>
  {:else}
  No clearances earned
  {/if}
  </CardText>
</CardBody>
<CardFooter class="d-flex">
  <Dropdown autoClose={true} >
  <DropdownToggle caret>Actions</DropdownToggle>
    <DropdownMenu>
      <DropdownItem on:click={refresh(c.neon_id)}>Refresh Attendees</DropdownItem>

      {#if c.supply_state != 'Supplies Requested'}
      <DropdownItem on:click={() => supply(false)}>Supplies needed</DropdownItem>
      {/if}
      {#if c.supply_state != 'Supplies Confirmed'}
      <DropdownItem on:click={() => supply(true)}>Supplies OK</DropdownItem>
      {/if}

      <DropdownItem divider/>

      <DropdownItem href="https://form.asana.com/?k=syF2O04JfU-Z82q6NcEJKg&d=1199692158232291" target="_blank">Purchase Request</DropdownItem>
      {#if c.volunteer}
        <DropdownItem on:click={() => volunteer(false)}>Switch to Paid</DropdownItem>
      {:else}
        <DropdownItem on:click={() => volunteer(true)}>Volunteer</DropdownItem>
      {/if}

      <DropdownItem divider/>

      {#if c.neon_id}
	<DropdownItem on:click={() => submit_log(c.prefill)}>Submit Log</DropdownItem>
      {/if}


      {#if !c.neon_id}
	{#if c.confirmed}
	<DropdownItem on:click={() => confirm(null)}>Unconfirm</DropdownItem>
	{:else}
        <DropdownItem on:click={() => confirm(true)}>Confirm available</DropdownItem>
	{/if}
	<DropdownItem divider />
        <DropdownItem on:click={() => confirm(false)}>Mark unavailable (hides permanently)</DropdownItem>
      {:else}
	<DropdownItem divider />
	<DropdownItem on:click={() => cancel(c.neon_id)}>Cancel class (requires no attendees)</DropdownItem>
      {/if}
    </DropdownMenu>
  </Dropdown>
</CardFooter>
</Card>
{:catch error}
  <FetchError {error}/>
{/await}
