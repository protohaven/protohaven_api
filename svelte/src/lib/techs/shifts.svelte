<script type="typescript">

import {onMount} from 'svelte';
import { TabPane, Table, Accordion, AccordionItem, Button, Row, Container, Col, Card, CardHeader, CardTitle, Modal, CardSubtitle, CardText, Icon, Tooltip, CardFooter, CardBody, Input, Spinner, FormGroup, Navbar, NavbarBrand, Nav, NavItem, Toast, ToastBody, ToastHeader } from '@sveltestrap/sveltestrap';
import Editor from './forecast_override.svelte';
import FetchError from '../fetch_error.svelte';
import {get, post} from '$lib/api.ts';

export let user;
let promise = new Promise((resolve) => {});
function refresh() {
  promise = get("/techs/forecast");
}
onMount(refresh);

let edit = null;

function start_edit(s) {
 let e = {ap: s.ap, date: s.date, techs: s.people, ...user};
 if (s.ovr) {
   e = {...e, id: s.ovr.id, orig: s.ovr.orig, editor: s.ovr.editor};
 }
  edit = e;
}

</script>

<TabPane tabId="schedule" tab="Cal" active>
<Card>
  <CardHeader>
  <CardTitle>Calendar</CardTitle>
  <p>An editable forecast of upcoming shifts.</p>
  </CardHeader>
<CardBody>
{#await promise}
	<Spinner/>Loading...
{:then p}
  <div class="d-flex flex-wrap">
	{#each p.calendar_view as cv}
	<div class="my-4" width="120px">
		{#each cv as v}
		<div class="mx-2">
		  <Button id={v.id} class="p-2 mx-2" color={v.color} on:click={() => start_edit(v)}>
		  {#if v.ovr}*{/if}
		  {v.title}
		  </Button>
		</div>
		<Tooltip target={v.id} placement="top">
		  {#if v.people.length === 0}
			Nobody is on shift!
		  {:else}
			{#each v.people as ppl}<div>{ppl}</div>{/each}
		  {/if}
		</Tooltip>
		{/each}
	</div>
	{/each}
  </div>

{:catch error}
  <FetchError {error}/>
{/await}
</CardBody>
<CardFooter>
  <p>
    Legend:
    <Button color='success'>3+ Techs</Button>
    <Button color='info'>2 Techs</Button>
    <Button color='warning'>1 Tech</Button>
    <Button color='danger'>0 Techs</Button>
  </p>
  <p><em>* indicates overridden shift info</em></p>
</CardFooter>
</Card>
</TabPane>

<Editor {edit} on_update={refresh}/>
