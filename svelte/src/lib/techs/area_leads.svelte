<script type="typescript">

import {onMount} from 'svelte';
import { Table, Button, Row, Col, Card, CardHeader, Badge, CardTitle, Modal, CardSubtitle, CardText, Icon, Tooltip, CardFooter, CardBody, Input, Spinner, FormGroup, Navbar, NavbarBrand, Nav, NavItem, Toast, ToastBody, ToastHeader } from '@sveltestrap/sveltestrap';
import {get} from '$lib/api.ts';

let promise = new Promise((resolve) => {});
function refresh() {
  promise = get("/techs/area_leads")
}
onMount(refresh);
</script>

<Card style="width: 100%" class="my-3">
  <CardHeader><CardTitle>Areas</CardTitle></CardHeader>
  <CardBody>
{#await promise}
<Spinner/>
{:then p}
  <Row>
  {#each Object.keys(p) as area}
    <Col class="my-3">
      <Card color={(p[area].length) ? null : 'warning'}>
      <CardHeader><CardTitle>{area}</CardTitle></CardHeader>
      <CardBody>
	{#each p[area] as name}
	  <div>{name}</div>
	{/each}
      </CardBody>
      </Card>
    </Col>
  {/each}
  </Row>
{/await}
  </CardBody>
</Card>
