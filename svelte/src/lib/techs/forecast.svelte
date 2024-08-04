<script type="ts">

import {onMount} from 'svelte';
import { Accordion, AccordionItem, Table, Button, Row, Container, Col, Card, CardHeader, CardTitle, Modal, CardSubtitle, CardText, Icon, Tooltip, CardFooter, CardBody, Input, Spinner, FormGroup, Navbar, NavbarBrand, Nav, NavItem, Toast, ToastBody, ToastHeader } from '@sveltestrap/sveltestrap';
import Editor from './forecast_override.svelte';
import FetchError from '../fetch_error.svelte';
import {get, post} from '$lib/api.ts';

export let email;
let promise = new Promise((resolve) => {});
function refresh() {
  promise = get("/techs/forecast")
}
onMount(refresh);

let edit = null;

function start_edit(s) {
  edit = {ap: s.ap, date: s.date, techs: s.people, id: s.ovr};
}

</script>

<Card style="width: 100%" class="my-3">
  <CardHeader>
    <CardTitle>Shift Swaps</CardTitle>
  </CardHeader>
  <CardBody>
{#await promise}
	<Spinner/>
{:then p}
  <Accordion>
    <AccordionItem>
			<h4 slot="header">Missing Coverage</h4>
			{#each p.coverage_missing as s}
				<Card>
					<div>{s.fields['Date']} - {s.fields['Shop Tech']}</div>
				</Card>
			{/each}
    </AccordionItem>
    <AccordionItem>
			<h4 slot="header">Covered Swaps</h4>
			{#each p.coverage_ok as s}
				<Card>
					<div>
						{s.fields['Date']} - Shop Tech: {s.fields['Shop Tech']}
						covered by {s.fields['Covered By'] || 'NONE'}
					</div>
				</Card>
			{/each}
    </AccordionItem>
  </Accordion>
  <h2>Forecast</h2>
  <div class="my-3">
    <p>
			Legend:
			<Button color='success'>3+ Techs</Button>
			<Button color='info'>2 Techs</Button>
			<Button color='warning'>1 Tech</Button>
			<Button color='danger'>0 Techs</Button>
			<em>* indicates overridden shift info</em>
    </p>
    <p>Hover over a day for details on shift coverage:</p>
  </div>
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
</Card>

<Editor {edit} {email} on_update={refresh}/>
