<script type="ts">

import {onMount} from 'svelte';
import { Table, Button, Row, Col, Card, CardHeader, Alert, CardTitle, CardSubtitle, CardText, Icon, CardFooter, CardBody, Input, Spinner, FormGroup, Navbar, NavbarBrand, Nav, NavItem } from '@sveltestrap/sveltestrap';
import ClassCard from './class_card.svelte';
import {get, post} from '$lib/api.ts';
import FetchError from './fetch_error.svelte';

let classes = [];
let readiness = {};
export let email;
export let scheduler_open; // Watched to trigger refresh

let promise;
function refresh() {
  promise = get("/instructor/class_details?email=" + email).then((data) => data.schedule);
}

$: {
  if (!scheduler_open) {
    refresh();
  }
}

</script>

<div style="width: 40vw; margin-left: 20px;">

{#await promise}
<Spinner/>
{:then classes}
{#if classes }
  {#each classes as c}
    {#if !c['Rejected']}
    <ClassCard eid={c[0]} c_init={c[1]}/>
    {/if}
  {/each}


  {#if classes.length == 0}
  <Alert class="my-3" color="warning">
    <em>No classes found - please schedule more using the Scheduler button on the left.</em>
  </Alert>
  {/if}

  <Button on:click={refresh}><Icon name="arrow-clockwise"/>Refresh Class List</Button>

{:else}
  Loading...
{/if}
{:catch error}
  <FetchError {error}/>
{/await}
</div>
