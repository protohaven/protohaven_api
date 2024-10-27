<script type="typescript">

import {onMount} from 'svelte';
import { ListGroup, ListGroupItem, Button, Card, CardHeader, CardTitle, CardSubtitle, CardBody, Input, Spinner } from '@sveltestrap/sveltestrap';

import FetchError from '../fetch_error.svelte';
import {post, get} from '$lib/api.ts';

export let user;
let loading = false;
let promise = new Promise((r,_)=>{r([])});
function reload() {
  loading = true;
  promise = get('/techs/events').finally(() => loading = false);
}
onMount(reload);

let submitting = false;
let submission = new Promise((r, _) => r(null));
function action(event_id, ticket_id, action) {
  submitting = true;
  submission = post('/techs/event', {event_id, ticket_id, action}).then(result => console.log(result)).finally(() => {
    reload();
    submitting = false;
  });
}
</script>

<Card>
<CardHeader>
  <CardTitle>Events for Backfill</CardTitle>
  <CardSubtitle>Register to fill open seats on upcoming events!</CardSubtitle>
</CardHeader>
<CardBody>
    <p>Note: you will need to pay the cost of materials when you show up.</p>
    <p>You can pay at the front desk via Square (select "Walk-In (3 Hr Class / add price)", set to the cost listed above, charge as normal)</p>
    {#if !user }
      <p><strong>You must <a href="/login">login</a> to register.</strong></p>
    {:else}
      <p>Click Register on events below to register as <br/><strong>{user.fullname}</strong> ({user.email})</p>
    {/if}
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
    <ListGroup>
    {#each p as r}
      <ListGroupItem>
            <div><strong>{r.name}</strong></div>
            <div>On {new Date(r.start).toLocaleString()}</div>
            <div><a href={`https://protohaven.org/e/${r.id}`} target="_blank">Event Details</a></div>
            <div>{r.capacity - r.attendees.length} seat(s) left</div>
            {#if user}
            <div>
            {#if r.attendees.indexOf(user.neon_id) !== -1}
              <strong>You are registered!</strong>
              <Button color="secondary" on:click={()=>action(r.id, r.ticket_id, 'unregister')} disabled={submitting}>Unregister</Button>
            {:else}
              <Button color="primary" on:click={()=>action(r.id, r.ticket_id, 'register')} disabled={submitting}>Register</Button>
            {/if}
            </div>
            {/if}
      </ListGroupItem>
    {/each}
    </ListGroup>
    {:catch error}
      <FetchError {error}/>
    {/await}
</CardBody>
</Card>
