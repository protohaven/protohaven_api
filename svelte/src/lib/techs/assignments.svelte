
<script type="typescript">

import {onMount} from 'svelte';
import { TabPane, Table, Accordion, AccordionItem, Button, Row, Container, Col, Card, CardHeader, CardTitle, Modal, CardSubtitle, CardText, Icon, Tooltip, CardFooter, CardBody, Input, Spinner, FormGroup, Navbar, NavbarBrand, Nav, NavItem, Toast, ToastBody, ToastHeader } from '@sveltestrap/sveltestrap';
import FetchError from '../fetch_error.svelte';
import {get, post} from '$lib/api.ts';

let promise = new Promise((resolve) => {});
function refresh() {
  promise = get("/techs/shifts");
}
onMount(refresh);
</script>

<TabPane tabId="assignments" tab="Shifts" active>
<Card>
  <CardHeader>
    <CardTitle>Shifts Assigned</CardTitle>
    <CardSubtitle>Every tech is assigned a regular shift.</CardSubtitle>
  </CardHeader>
<CardBody>
{#await promise}
<Spinner/>Loading...
{:then p}

<Table class="my-3">
  <thead>
    <th></th>
	{#each ['AM', 'PM'] as ap}
	  <th class="mx-3 text-center">{ap}</th>
	{/each}
      </thead>
      <tbody>
	{#each ['', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'] as d}
	<tr>
	  <td class="text-end align-middle"><strong>{d}</strong></td>
	{#each ['AM', 'PM'] as ap}
	  <td>
	  {#each p[d + ' ' + ap] || [] as sm}
	    <Card class="my-2 p-2">{sm}</Card>
	  {/each}
	  </td>
	{/each}
	</tr>
	{/each}
  </tbody>
</Table>
{/await}
</CardBody>
</Card>
</TabPane>
