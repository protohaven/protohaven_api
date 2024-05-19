<script type="ts">

import {onMount} from 'svelte';
import { Table, Button, Row, Col, Card, CardHeader, Badge, CardTitle, Modal, CardSubtitle, CardText, Icon, Tooltip, CardFooter, CardBody, Input, Spinner, FormGroup, Navbar, NavbarBrand, Nav, NavItem, Toast, ToastBody, ToastHeader } from '@sveltestrap/sveltestrap';
import {get} from '$lib/api.ts';

let promise = new Promise((resolve) => {});
function refresh() {
  promise = get("/techs/tool_state");
}
onMount(refresh);
</script>


<Card style="width: 100%" class="my-3">
  <CardHeader><CardTitle>Tool States</CardTitle></CardHeader>
  <CardBody>
{#await promise}
<Spinner/>
{:then p}
  {#each Object.keys(p) as color}
    {#if !color.startsWith('Green') && !color.startsWith('Grey')}
    <Row>
      <CardHeader><CardTitle>{color.split(' ')[0]}</CardTitle></CardHeader>
      <CardBody>
      {#each p[color] as tool}
	<Badge color="light">{tool.name} ({tool.modified} days)</Badge>
      {/each}
      </CardBody>
    </Row>
    {/if}
  {/each}
  {/await}
  </CardBody>
</Card>
