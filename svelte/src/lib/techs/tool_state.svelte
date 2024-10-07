<script type="typescript">

import {onMount} from 'svelte';
import { Table, Button, Row, Col, Card, CardHeader, Badge, CardTitle, Popover, Modal, CardSubtitle, CardText, Icon, Tooltip, CardFooter, CardBody, Input, Spinner, FormGroup, Navbar, NavbarBrand, Nav, NavItem, Toast, ToastBody, ToastHeader } from '@sveltestrap/sveltestrap';
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
	<em>Click on any badge to see more details, make tool reports, documentation etc.</em>

{#await promise}
<Spinner/>
{:then p}
  {#each Object.keys(p) as color}
    {#if !color.startsWith('Green') && !color.startsWith('Grey')}
    <Row>
      <CardBody>
      {#each p[color] as tool}
	<Badge class="mx-2" id="btn-{tool.code}" color={get_color(color)}>{tool.name} ({tool.modified} days)</Badge>
        <Popover target="btn-{tool.code}" title={tool.name} hideOnOutsideClick>
		<div>{tool.date}</div>
		<div>{tool.message}</div>
	    	<div><a href="https://airtable.com/appbIlORlmbIxNU1L/shr9Hbyf7tdf7Y5LD/tblalZYdLVoTICzE6?filter_Tool Name={tool.name}" target="_blank">more info</a></div>
	</Popover>
      {/each}
      </CardBody>
    </Row>
    {/if}
  {/each}
  {/await}
  </CardBody>
</Card>
