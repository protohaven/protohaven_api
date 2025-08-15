<script type="typescript">

import {onMount} from 'svelte';
import { FormGroup, Label, Accordion, AccordionItem, ListGroup, ListGroupItem, Button, Card, CardHeader, CardTitle, CardSubtitle, CardBody, Input, Spinner } from '@sveltestrap/sveltestrap';

import FetchError from '../fetch_error.svelte';
import {get, isodate} from '$lib/api.ts';


let start_date = new Date();

export let visible;
let search = "";
let promise = new Promise((r,_)=>{r([])});
let loaded = false;
function refresh() {
  const start = isodate(new Date(start_date));
  promise = get(`/techs/members?start=${start}`).then((data) => {
    loaded = true;
    let by_email = {};
    for (let d of data) {
      d.created = new Date(d.created);
      console.log(d);
      if (!by_email[d['email']]) {
        by_email[d['email']] = {...d, "timestamps": new Set()};
      }
      by_email[d['email']]['timestamps'].add(d.created.toLocaleTimeString());
    }
    let results = Object.values(by_email);
    // Sort descending, newest on top
    results.sort((a, b) => b.created - a.created);
    return results;
  });
}
$: {
  if (visible && !loaded) {
    refresh();
  }
}

</script>

{#if visible}
<Card>
<CardHeader>
  <CardTitle>Member Check</CardTitle>
  <CardSubtitle>Today's sign-ins, including membership state and clearances</CardSubtitle>
</CardHeader>
<CardBody>
    {#await promise}
      <Spinner/>Loading...
    {:then p}
    <FormGroup>
      <Label>Start Date</Label>
      <Input type="date" bind:value={start_date} on:change={refresh}/>
    </FormGroup>

    <ListGroup>
    {#each p as r}
      <ListGroupItem>
        <p><strong>{r.email}{#if r.name}&nbsp;({r.name}){/if}</strong>
          {r.created.toLocaleTimeString()} -
              {#if !r.member}
                Guest
              {:else}
                  Member (<span style={(r.status !== 'Active') ? 'background-color: yellow;' : null}}>{r.status}</span>)
              {/if}
        </p>
        {#if r.timestamps.size > 1}
        <p>All event timestamps: {Array.from(r.timestamps).join(", ")}</p>
        {/if}
        {#if !r.clearances.length && !r.violations.length}
          <p>No clearances, no violations</p>
        {:else}
          <Accordion>
            {#if r.clearances.length}
              <AccordionItem header={r.clearances.length + ' clearance(s)'}>
                <ListGroup>
                {#each r.clearances as c}
                  <ListGroupItem>{c}</ListGroupItem>
                {/each}
                </ListGroup>
              </AccordionItem>
            {/if}
            {#if r.violations.length}
              <AccordionItem>
                <p class="m-0" slot="header" style={(r.violations.length) ? 'background-color: yellow;' : null}>{r.violations.length + ' violation(s)'}</p>
                <ListGroup>
                {#each r.violations as v}
                  <ListGroupItem>{v}</ListGroupItem>
                {/each}
                </ListGroup>
              </AccordionItem>
            {/if}
          </Accordion>
        {/if}
      </ListGroupItem>
    {/each}
    </ListGroup>
    {:catch error}
      <FetchError {error}/>
    {/await}
</CardBody>
</Card>
{/if}
