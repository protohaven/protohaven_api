<script type="typescript" lang="ts">

import {onMount} from 'svelte';
import { Table, Button, Row, Col, Card, CardHeader, Alert, CardTitle, CardSubtitle, CardText, Icon, CardFooter, CardBody, Input, Spinner, FormGroup, Navbar, NavbarBrand, Nav, NavItem } from '@sveltestrap/sveltestrap';
import ClassCard from './class_card.svelte';
import {get, post} from '$lib/api.ts';
import FetchError from '../fetch_error.svelte';

let readiness = {};
export let email;
export let scheduler_open; // Watched to trigger refresh

let promise;
let submissions = {};

async function refresh() {
  promise = get("/instructor/class_details?email=" + encodeURIComponent(email)).then((data)=>{
    console.log(data);
    return data.schedule;
  });
  get("/instructor/submissions?email=" + encodeURIComponent(email)).then((data) => {
    submissions = data;
  }).catch(err => {
    console.warn("Failed to fetch instructor submissions:", err);
    return {}; // Return empty object if submissions fetch fails
  })
}

$: {
  if (!scheduler_open) {
    refresh();
  }
}

</script>

{#await promise}
<Spinner/>
{:then classes}
{#if classes }
  {#each classes as c}
    {#if !c['Rejected']}
      <ClassCard schedule_id={c.schedule_id} c_init={c} {submissions}/>
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
