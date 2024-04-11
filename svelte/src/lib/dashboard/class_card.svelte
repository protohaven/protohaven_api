<script type="ts">
import { onMount } from 'svelte';
import { Button, Row, Col, Card, CardHeader, CardTitle, CardSubtitle, CardText, CardFooter, CardBody, Input, Spinner, FormGroup, Dropdown, DropdownMenu, DropdownItem, DropdownToggle, Navbar, NavbarBrand, Nav, NavItem, Alert } from '@sveltestrap/sveltestrap';

export let eid;
export let base_url;

export let c_init;
let meta_promise = Promise.resolve(c_init);


let attendees = [];

function fetch_attendees(data) {
  if (data['Neon ID']) {
    console.log("Fetching attendees for", data['Neon ID']);
    return fetch(base_url + "/instructor/class/attendees?id=" + data['Neon ID']).then((rep) => rep.json()).then((data) => {
      attendees = data;
      return data;
    });
  }
  return [];
}
let promise = meta_promise.then(fetch_attendees);


function refresh(neon_id) {
  if (neon_id) {
    promise = fetch(base_url + "/instructor/class/attendees?id=" + neon_id).then((rep) => rep.json());
  }
  return promise;
}
//onMount(refresh);

function post_json(url, data) {
  meta_promise = fetch(base_url + url, {
    method: 'POST',
    headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data),
  }).then((rep) => rep.json());
  promise = meta_promise.then(fetch_attendees);
}

function confirm(pub) {
  return post_json("/instructor/class/update", {eid, pub});
}

function submit_log(url) {
  let attendees_for_log = [];
  for (let d of attendees) {
    attendees_for_log.push(`${d.firstName} ${d.lastName} (${d.email})`);
  }
  url = url.replace("$ATTENDEE_NAMES", encodeURIComponent(attendees_for_log.join(", ")));
  window.open(url, "_blank");
}

function supply(ok) {
  return post_json("/instructor/class/supply_req", {eid, missing: !ok});
}

function volunteer(v) {
  return post_json("/instructor/class/volunteer", {eid, volunteer: v});
}
</script>

{#await meta_promise}
  <Spinner/>
{:then c}
<Card class="my-3" size={'lg'}>
<CardHeader style={(c['Neon ID']) ? "background-color: rgb(230, 225, 249)" : ""}>
  <CardTitle>
    {#if c['Neon ID']}
      <i class="bi bi-calendar-check"></i>
    {:else}
      <i class="bi bi-question-circle"></i> PROPOSED:
    {/if}
    {c['Name (from Class)'][0]}
  </CardTitle>
</CardHeader>
<CardBody>
  {#if c['Rejected']}
    <Alert color="warning" class="mx-3">This card will disappear upon refreshing the page.</Alert>
  {/if}

  <CardSubtitle>Dates:</CardSubtitle>
  <CardText>
    <ul>
      {#each c.Dates as d}
      <li>{d}</li>
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
	<li>{a.firstName} {a.lastName} ({a.email}) {a.registrationStatus} on {a.registrationDate}</li>
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
  <li># Seats:  {c['Capacity (from Class)'][0]}</li>
  <li>{c['Supply State']} </li>
  <li>Instruction: {#if c['Volunteer']}Volunteer (no pay){:else}Paid{/if} </li>
  <li>Instructor confirmed:  {#if c['Confirmed']}on {c['Confirmed']}{:else}no{/if}</li>
  </ul>
  </CardText>
</CardBody>
<CardFooter class="d-flex">
  <Dropdown autoClose={true} >
  <DropdownToggle caret>Actions</DropdownToggle>
    <DropdownMenu>
      <DropdownItem on:click={refresh(c['Neon ID'])}>Refresh Attendees</DropdownItem>

      {#if c['Supply State'] != 'Supplies Requested'}
      <DropdownItem on:click={() => supply(false)}>Supplies needed</DropdownItem>
      {/if}
      {#if c['Supply State'] != 'Supplies Confirmed'}
      <DropdownItem on:click={() => supply(true)}>Supplies OK</DropdownItem>
      {/if}

      <DropdownItem divider/>

      <DropdownItem href="https://form.asana.com/?k=syF2O04JfU-Z82q6NcEJKg&d=1199692158232291" target="_blank">Purchase Request</DropdownItem>
      {#if c['Volunteer']}
        <DropdownItem on:click={() => volunteer(false)}>Switch to Paid</DropdownItem>
      {:else}
        <DropdownItem on:click={() => volunteer(true)}>Volunteer</DropdownItem>
      {/if}

      <DropdownItem divider/>

      {#if c['Neon ID']}
	<DropdownItem on:click={() => submit_log(c['prefill'])}>Submit Log</DropdownItem>
      {/if}



      {#if !c['Neon ID']}
	{#if c['Confirmed']}
	<DropdownItem on:click={() => confirm(null)}>Unconfirm</DropdownItem>
	{:else}
        <DropdownItem on:click={() => confirm(true)}>Confirm available</DropdownItem>
	{/if}
	<DropdownItem divider />
        <DropdownItem on:click={() => confirm(false)}>Mark unavailable (hides permanently)</DropdownItem>
      {/if}
    </DropdownMenu>
  </Dropdown>
</CardFooter>
</Card>
{/await}
