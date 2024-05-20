<script type="ts">

import {onMount} from 'svelte';
import { Table, Button, Row, Container, Col, Card, CardHeader, Badge, CardTitle, Modal, CardSubtitle, CardText, Icon, Tooltip, CardFooter, CardBody, Input, Spinner, FormGroup, Navbar, NavbarBrand, Nav, NavItem, Toast, ToastBody, ToastHeader } from '@sveltestrap/sveltestrap';
import {get, post} from '$lib/api.ts';

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
  <Row cols={{ xxl: 2, xl: 2, l: 2, m: 2, s: 1, xs: 1}}>
    <Col>
			<h2>Missing Coverage</h2>
			{#each p.coverage_missing as s}
				<Card>
					<div>{s.fields['Date']} - {s.fields['Rendered Shop Tech']}</div>
				</Card>
			{/each}
    </Col>
    <Col>
			<h2>Covered Swaps</h2>
			{#each p.coverage_ok as s}
				<Card>
					<div>
						{s.fields['Date']} - Shop Tech: {s.fields['Rendered Shop Tech']}
						covered by {s.fields['Rendered Covered By'] || 'NONE'}
					</div>
				</Card>
			{/each}
    </Col>
  </Row>
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
{/await}
  </CardBody>
</Card>
