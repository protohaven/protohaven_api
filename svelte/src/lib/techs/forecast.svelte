<script type="ts">

import {onMount} from 'svelte';
import { Accordion, AccordionItem, Table, Button, Row, Container, Col, Card, CardHeader, Badge, CardTitle, Modal, CardSubtitle, CardText, Icon, Tooltip, CardFooter, CardBody, Input, Spinner, FormGroup, Navbar, NavbarBrand, Nav, NavItem, Toast, ToastBody, ToastHeader } from '@sveltestrap/sveltestrap';
import {get, post} from '$lib/api.ts';

let shift_edit_date = null;
let shift_edit_techs = [];
let adjust_promise = new Promise((resolve) => {});
function forecast_date() {
  adjust_promise = get("/techs/forecast?days=1&date=" + shift_edit_date).then((data) => {
    shift_edit_techs = data.calendar_view;
  });
}
function override_forecast() {
  adjust_promise = post("/techs/override", {date: shift_edit_date, techs: shift_edit_techs});
}

let promise = new Promise((resolve) => {});
function refresh() {
  promise = get("/techs/forecast")
}
onMount(refresh);
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
					<div>{s.fields['Date']} - {s.fields['Rendered Shop Tech']}</div>
				</Card>
			{/each}
    </AccordionItem>
    <AccordionItem>
			<h4 slot="header">Covered Swaps</h4>
			{#each p.coverage_ok as s}
				<Card>
					<div>
						{s.fields['Date']} - Shop Tech: {s.fields['Rendered Shop Tech']}
						covered by {s.fields['Rendered Covered By'] || 'NONE'}
					</div>
				</Card>
			{/each}
    </AccordionItem>
  </Accordion>
  <h2>Forecast</h2>
  <div class="my-3">
    <p>
			Legend:
			<Badge color='success'>3+ Techs</Badge>
			<Badge color='info'>2 Techs</Badge>
			<Badge color='warning'>1 Tech</Badge>
			<Badge color='danger'>0 Techs</Badge>
    </p>
    <p>Hover over a day for details on shift coverage:</p>
  </div>
  <div class="d-flex flex-wrap">
	{#each p.calendar_view as cv}
	<div class="my-4" width="120px">
		{#each cv as v}
		<div class="mx-2"><Badge id={v.id} class="p-2 mx-2" color={v.color}>{v.title}</Badge></div>
		<Tooltip target={v.id} placement="top">
			{#each v.people as ppl}<div>{ppl}</div>{/each}
		</Tooltip>
		{/each}
	</div>
	{/each}
  </div>

  <hr/>
  <div>
    Adjust coverage for date: <Input on:change={forecast_date} class="mx-1" type="date" bind:value={shift_edit_date}/>
    {#await adjust_promise}
      <Spinner/>
    {:then p2}
	{#each shift_edit_techs as shift}
	<h4>{shift.title}</h4>
	  {#each shift.people as person}
	    <div>{person} <Button>-</Button></div>
	  {/each}
	    <Input type="select">
		<option>Add a Tech...</option>
	    </Input>
	{/each}
    {/await}
  </div>

{/await}
  </CardBody>
</Card>
