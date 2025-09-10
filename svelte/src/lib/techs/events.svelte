<script type="typescript">

import {onMount} from 'svelte';
import { Row, Col, Form, FormGroup, ListGroup, ListGroupItem, Button, Card, CardHeader, CardTitle, CardSubtitle, CardBody, Input, Spinner } from '@sveltestrap/sveltestrap';

import FetchError from '../fetch_error.svelte';
import {post, get} from '$lib/api.ts';

export let visible;
let loaded = false;
export let user;
let loading = false;
let promise = new Promise((r,_)=>{r([])});
function reload() {
  loading = true;
  promise = get('/techs/events').then((data) => {loaded=true; return data;}).finally(() => loading = false);
}
$: {
  if (visible && !loaded) {
    reload();
  }
}

let submitting = false;
let submission = new Promise((r, _) => r(null));
function action(event_id, ticket_id, action) {
  submitting = true;
  submission = post('/techs/event', {event_id, ticket_id, action}).then(result => console.log(result)).finally(() => {
    reload();
    submitting = false;
  });
}

let new_event_form = {
  "name": null,
  "capacity": 6,
  "start": null,
  "hours": 3,
};
function new_tech_event() {
  if (!new_event_form.name || !new_event_form.name.trim().length) {
    alert("Please name your tech class");
    return;
  }
  let d = new Date(new_event_form.start);
  if (d < new Date()) {
    alert("Start date must be set, and in the future");
    return;
  }
  console.log("Date parsed as", d);
  console.log(new_event_form);
  if (d.getHours() < 10 || d.getHours() + parseInt(new_event_form.hours, 10) > 22) {
    alert("Event must start and end within shop hours (10AM-10PM); please check date and hours form values");
    return;
  }
  console.log("Create event", new_event_form);
  submitting = true;
  submission = post('/techs/new_event', new_event_form).then(result => {
    console.log(result);
  }).finally(() => {
    reload();
    submitting = false;
  });
}

function delete_event(eid) {
  submitting = true;
  submission = post('/techs/rm_event', {eid}).then(result => {
    console.log(result);
  }).finally(() => {
    reload();
    submitting = false;
  });
}

</script>

{#if visible}
<Card>
<CardHeader>
  <CardTitle>Events for Backfill</CardTitle>
  <CardSubtitle>Register to fill open seats on upcoming events!</CardSubtitle>
</CardHeader>
<CardBody>
    <p>Note: you will need to pay the cost of materials when you show up.</p>
    <p>You can pay at the front desk via Square - select "Walk-In (3 Hr Class / add price)", set to the cost listed above, charge as normal.</p>
    {#await promise}
      <Spinner/>loading...
    {:then p}
    {#await submission}
      <Spinner/>
    {:then s}
    {#if s}
        {JSON.stringify(s)}
    {/if}
    {:catch error}
    <FetchError {error}/>
    {/await}
    {#if p.length === 0}
      <em>No event available for backfill - please check back later.</em>
    {:else if !user || !p.can_register}
      <p><strong>You must <a href="http://api.protohaven.org/login">login</a> as a Shop Tech or Tech Lead to register for events.</strong></p>
    {:else}
      <p>Click Register on events below to register as <br/><strong>{user.fullname}</strong> ({user.email})</p>
    {/if}
    <ListGroup>
    {#each p.events as r}
      <ListGroupItem>
            <div><strong>{r.name}</strong></div>
            <div>On {new Date(r.start).toLocaleString()}</div>
            <div><a href={`https://protohaven.org/e/${r.id}`} target="_blank">Event Details</a></div>
            <div>{r.capacity - r.attendees.length} seat(s) left</div>
            {#if user && p.can_register}
            <div>
            {#if r.attendees.indexOf(user.neon_id) !== -1}
              <strong>You are registered!</strong>
              <Button color="secondary" on:click={()=>action(r.id, r.ticket_id, 'unregister')} disabled={submitting}>Unregister</Button>
            {:else if r.capacity - r.attendees.length > 0}
              <Button color="primary" on:click={()=>action(r.id, r.ticket_id, 'register')} disabled={submitting}>Register</Button>
            {/if}
            {#if p.can_edit && r.name.startsWith("(SHOP TECH ONLY)")}
              <Button color="secondary" class="mx-4" on:click={()=>delete_event(r.id)}>Delete Permanently</Button>
            {/if}
            </div>
            {/if}
      </ListGroupItem>
    {/each}
    </ListGroup>

    {#if p.can_edit}
    <h4 class="my-2">Create a new event for techs</h4>
    <p>Note: this event is unlisted and will not appear on the <a href="protohaven.org/classes/">Classes and Events</a> page. Event creation is only visible to logged-in users with the Tech Leads role set in Neon CRM.</p>

    <Form>
      <FormGroup>
        <Row>
          <Col md="6">
            <span>Class name:</span>
            (SHOP TECH ONLY) <Input type="text" id="class_name" label="Class Name" bind:value={new_event_form.name} />
          </Col>
          <Col md="6">
            <span>Max participants:</span>
            <Input type="number" id="capacity" label="Capacity" bind:value={new_event_form.capacity}/>
          </Col>
        </Row>
        <Row>
          <Col md="6">
            <span>Start date and time:</span>
            <Input type="datetime-local" id="start" label="Start Time" bind:value={new_event_form.start}/>
          </Col>
          <Col md="6">
            <span>Duration (hours)</span>
            <Input type="number" id="hours" label="Duration (hours)" bind:value={new_event_form.hours}/>
          </Col>
        </Row>
        <Row>
          <Col md="12" class="d-flex justify-content-end">
            <Button on:click={new_tech_event} type="submit" color="primary">Submit</Button>
          </Col>
        </Row>
      </FormGroup>
    </Form>

    <hr/>
    {/if}


    {:catch error}
      <FetchError {error}/>
    {/await}
</CardBody>
</Card>
{/if}
