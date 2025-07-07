<script type="typescript">

import {onMount} from 'svelte';
import { Table, Button, Row, Col, Card, CardHeader, Badge, CardTitle, Modal, CardSubtitle, CardText, Icon, Tooltip, CardFooter, CardBody, Input, Spinner, FormGroup, Navbar, NavbarBrand, Nav, NavItem, Toast, ToastBody, ToastHeader } from '@sveltestrap/sveltestrap';
import {get} from '$lib/api.ts';

export let visible;
let loaded = false;
let promise = new Promise((resolve) => {});
function refresh() {
  promise = get("/techs/area_leads").then((data) => {loaded = true; return data;});
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
  <CardTitle>Areas &amp; Leads</CardTitle>
  <CardSubtitle>Contact points for different parts of the shop</CardSubtitle>
</CardHeader>
<CardBody>
{#await promise}
<Spinner/>
{:then p}
  {#each Object.keys(p['area_leads']) as area}
      <Card color={(p['area_leads'][area].length) ? null : 'warning'}>
      <CardHeader><CardTitle>{area}</CardTitle></CardHeader>
      <CardBody>
	{#each p['area_leads'][area] as tech}
	  <div>{tech.name}</div>
	  <div>{tech.email}</div>
	  <div>Shift: {tech.shift.join(' ')}</div>
	{/each}
      </CardBody>
      </Card>
  {/each}

  <h2 class="my-2">Additional Contacts</h2>
  <em>Contacts will appear here if they are assigned an "Area Lead" role for an area which is not tracked.</em>
  {#if Object.keys(p['other_leads']).length === 0}
    <p class="m-2">No additional contacts found.</p>
  {/if}
  {#each Object.keys(p['other_leads']) as a}
      <Card>
      <CardHeader><CardTitle>{a}</CardTitle></CardHeader>
      <CardBody>
	{#each p['other_leads'][a] as tech}
	  <div>{tech.name}</div>
	  <div>{tech.email}</div>
	  <div>Shift: {tech.shift}</div>
	{/each}
      </CardBody>
      </Card>
  {/each}
{/await}
</CardBody>
</Card>
{/if}
