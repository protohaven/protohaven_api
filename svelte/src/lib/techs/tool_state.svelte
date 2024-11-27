<script type="typescript">

import {onMount} from 'svelte';
import { Table, Button, Row, Col, Card, CardHeader, Badge, CardTitle, Popover, Modal, CardSubtitle, CardText, Icon, Tooltip, CardFooter, CardBody, Input, Spinner, FormGroup, Navbar, NavbarBrand, Nav, NavItem, Toast, ToastBody, ToastHeader } from '@sveltestrap/sveltestrap';
import {get} from '$lib/api.ts';

export let visible;
let loaded = false;
let promise = new Promise((resolve) => {});
function refresh() {
  promise = get("/techs/tool_state").then((data) => {loaded = true; return data;});
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

$: {
  if (visible && !loaded) {
    refresh();
  }
}
</script>

{#if visible}
<Card>
    <CardHeader><CardTitle>Tool Maintenance State</CardTitle>
    <CardSubtitle>Click on a tool to see details and make reports</CardSubtitle>
  </CardHeader>
  <CardBody>
{#await promise}
<Spinner/>
{:then p}
  {#each Object.keys(p) as color}
    {#if !color.startsWith('Green') && !color.startsWith('Grey')}
    <Row>
      <CardBody>
      {#each p[color] as tool}
	<Badge style="cursor: pointer" class="mx-2" id="btn-{tool.code}" color={get_color(color)}>{tool.name} ({tool.modified} days)</Badge>
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
  <CardFooter>
      Looking for a task? Check the <a href="https://app.asana.com/0/1202469740885594/1204138662113052" target="_blank">Shop & Maintenance Tasks<a/> Asana project.
  </CardFooter>
</Card>
{/if}
