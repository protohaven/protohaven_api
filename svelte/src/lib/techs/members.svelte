<script type="typescript">

import {onMount} from 'svelte';
import { Accordion, AccordionItem, ListGroup, ListGroupItem, Button, Card, CardHeader, CardTitle, CardSubtitle, CardBody, Input, Spinner } from '@sveltestrap/sveltestrap';

import FetchError from '../fetch_error.svelte';
import {get} from '$lib/api.ts';

export let visible;
let search = "";
let promise = new Promise((r,_)=>{r([])});
let loaded = false;
function refresh() {
  promise = get(`/techs/members`).then((data) => {
    loaded = true;
    let results = [];
    for (let d of data) {
      results.push({
        "timestamp": new Date(d['Created']),
        "member": d['Am Member'],
        "email": d['Email'],
        "clearances": (d['Clearances']) ? d['Clearances'].split(',').map(entry => entry.trim()) : [],
        "status": d['Status'] || 'UNKNOWN',
        "name": d['Full Name'] || null,
        "violations": (d['Violations']) ? d['Violations'].split(',').map(entry => entry.trim()): [],
      });
    }
    // Sort descending, newest on top
    results.sort((a, b) => b.timestamp - a.timestamp);
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
    <ListGroup>
    {#each p as r}
      <ListGroupItem>
        <p><strong>{r.email}{#if r.name}&nbsp;({r.name}){/if}</strong></p>
        <p> {r.timestamp.toLocaleTimeString()} -
              {#if !r.member}
                Guest
              {:else}
                  Member (<span style={(r.status !== 'Active') ? 'background-color: yellow;' : null}}>{r.status}</span>)
              {/if}
        </p>
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
