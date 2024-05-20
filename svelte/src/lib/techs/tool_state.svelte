<script type="ts">

import {onMount} from 'svelte';
import { Table, Button, Row, Col, Card, CardHeader, Badge, CardTitle, Modal, CardSubtitle, CardText, Icon, Tooltip, CardFooter, CardBody, Input, Spinner, FormGroup, Navbar, NavbarBrand, Nav, NavItem, Toast, ToastBody, ToastHeader } from '@sveltestrap/sveltestrap';
import {get} from '$lib/api.ts';

let promise = new Promise((resolve) => {});
function refresh() {
  promise = get("/techs/tool_state");
}
function get_color(status) {
  if (status.startsWith('Blue')) {
    return 'info';
  } else if (status.startsWith('Yellow')) {
    return 'warning';
  } else if (status.startsWith('Red')) {
    return 'danger';
  }
  return 'light';
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
      <CardBody>
      {#each p[color] as tool}
	<Badge class="mx-2" color={get_color(color)}>{tool.name} ({tool.modified} days)</Badge>
      {/each}
      </CardBody>
    </Row>
    {/if}
  {/each}
  {/await}
  </CardBody>
</Card>
