<script type="typescript">

import {onMount} from 'svelte';
import { TabPane, Table, Button, Row, Col, Card, CardHeader, Badge, CardTitle, Modal, CardSubtitle, CardText, Icon, Tooltip, CardFooter, CardBody, Input, Spinner, FormGroup, Navbar, NavbarBrand, Nav, NavItem, Toast, ToastBody, ToastHeader } from '@sveltestrap/sveltestrap';
import {get} from '$lib/api.ts';

let promise = new Promise((resolve) => {});
function refresh() {
  promise = get("/techs/area_leads")
}
onMount(refresh);
</script>

<TabPane tabId="area_leads" tab="Areas">
<Card>
<CardHeader>
  <CardTitle>Areas &amp; Leads</CardTitle>
  <CardSubtitle>Contact points for different parts of the shop</CardSubtitle>
</CardHeader>
<CardBody>
{#await promise}
<Spinner/>
{:then p}
  {#each Object.keys(p) as area}
      <Card color={(p[area].length) ? null : 'warning'}>
      <CardHeader><CardTitle>{area}</CardTitle></CardHeader>
      <CardBody>
	{#each p[area] as tech}
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
</TabPane>
