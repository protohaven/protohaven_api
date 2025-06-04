<script type="typescript">

import {onMount} from 'svelte';
import { Table, Dropdown, DropdownToggle, DropdownItem, DropdownMenu, Button, Row, Col, Card, CardHeader, Badge, CardTitle, Alert, Popover, Modal, CardSubtitle, CardText, Icon, Tooltip, CardFooter, CardBody, Input, Spinner, FormGroup, Navbar, NavbarBrand, Nav, NavItem, Toast, ToastBody, ToastHeader } from '@sveltestrap/sveltestrap';
import {get} from '$lib/api.ts';

export let visible;
let loaded = false;
let promise = new Promise((resolve) => {});

const URGENCY = [
  "Unknown",
  "Red (non-functional or unsafe)",
  "Yellow (usable with caution)",
  "Blue (needs set-up)",
  "Green (fully operational)",
];

let tool_state = null;
let tools_sorted = {};
let areas = new Set();
let area_filter = null;
let sort_type = "urgency";
let sort_name = {
  "state_age_asc": "Longest time in State",
  "state_age_desc": "Shortest time in State",
  "urgency": "Urgency (red/yellow/blue/green)",
  "name": "By Name",
};
function filter_by_area(a) {
  return !area_filter || (a.area.indexOf(area_filter) !== -1);
}
$: {
  if (tool_state) {
    if (area_filter) {
      console.log("Filter changed to", area_filter);
    }
    if (sort_type === "state_age_asc") {
      tools_sorted = [...tool_state].sort((a, b) => b.modified - a.modified).filter(filter_by_area);
    } else if (sort_type === "state_age_desc") {
      tools_sorted = [...tool_state].sort((a, b) => a.modified - b.modified).filter(filter_by_area);
    } else if (sort_type === "name") {
      tools_sorted = [...tool_state].sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase())).filter(filter_by_area);
    } else if (sort_type === "urgency") {
      tools_sorted = [...tool_state].sort((a, b) => URGENCY.indexOf(a.status) - URGENCY.indexOf(b.status)).filter(filter_by_area);
    }
  }
}

function resolve_docs_category(docs, cat) {
  let url = docs[`${cat}_not_found_url`];
  if (!docs || !docs[cat]) {
    return {status: 'missing', color: 'warning', url};
  }
  url = docs[cat][0]['url'];
  if (docs[cat].length != 1) {
    return {status: `expecting exactly 1 page, got ${docs[cat].length}`, color: 'warning', url};
  }
  if (!docs[cat][0]['approved_revision']) {
    const needed = docs[cat][0]['thresh'] - Object.keys(docs[cat][0]['approvals']).length;
    return {status: `page missing ${needed} approval(s)`, color: 'warning', url};
  }
  return {status: 'approved', color: 'success', url};
}

function refresh() {
  promise = Promise.all([get("/techs/tool_state"), get("/techs/docs_state")]).then((data) => {
    tool_state = [];
    let docs_state = data[1];
    areas = new Set();
    for (let tool of data[0]) {
      if (tool.status === "Grey (N/A)") {
        continue;
      }
      let docs = docs_state['by_code'][tool.code] || {};
      tool.clearance_doc = resolve_docs_category(docs, 'clearance');
      tool.tutorial_doc = resolve_docs_category(docs, 'tool_tutorial');
      tool_state.push(tool);
      for (let area of tool.area) {
        areas.add(area.trim());
      }
    }
    loaded = true;
  });
}
function get_color(status) {
  if (status.startsWith('Blue')) {
    return 'info';
  } else if (status.startsWith('Yellow')) {
    return 'warning';
  } else if (status.startsWith('Red')) {
    return 'danger';
  } else if (status.startsWith('Green')) {
    return 'success';
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
    {#if tools_sorted}
      <Dropdown>
          <DropdownToggle color="light" caret>
              Sort by {sort_name[sort_type]}
          </DropdownToggle>
          <DropdownMenu>
              {#each Object.keys(sort_name) as sn}
              <DropdownItem on:click={() => sort_type=(sn) }>{sort_name[sn]}</DropdownItem>
              {/each}
          </DropdownMenu>
      </Dropdown>
      <Dropdown>
          <DropdownToggle color="light" caret>
              {#if !area_filter}Show All Areas{:else }Show {area_filter}{/if}
          </DropdownToggle>
          <DropdownMenu>
              <DropdownItem on:click={() => area_filter=null}>All Areas</DropdownItem>
              {#each areas as a}
              <DropdownItem on:click={() => area_filter=a}>{a}</DropdownItem>
              {/each}
          </DropdownMenu>
      </Dropdown>

      {#each tools_sorted as tool}
        <Card>
          <CardHeader>{tool.name}
            <Badge class="mx-2" id="btn-{tool.code}" color={get_color(tool.status)}>{tool.date} ({tool.modified} day{#if tool.modified !== 1}s{/if} ago)</Badge>
          </CardHeader>
          <CardBody>
            <div>Code: {tool.code}</div>
            <div>Area: {tool.area}</div>
            <div>Status: {tool.message}</div>
            <div>Clearance doc: <Badge color={tool.clearance_doc.color} href={tool.clearance_doc.url} target="_blank">{tool.clearance_doc.status}</Badge></div>
            <div>Tutorial doc: <Badge color={tool.tutorial_doc.color} href={tool.tutorial_doc.url} target="_blank">{tool.tutorial_doc.status}</Badge></div>
            <div><a href="https://airtable.com/appbIlORlmbIxNU1L/shr9Hbyf7tdf7Y5LD/tblalZYdLVoTICzE6?filter_Tool Name={tool.name}" target="_blank">history</a></div>
          </CardBody>
        </Card>
      {/each}
    {/if}
    {/await}
  </CardBody>
  <CardFooter>
      Looking for a task? Check the <a href="https://app.asana.com/0/1202469740885594/1204138662113052" target="_blank">Shop & Maintenance Tasks<a/> Asana project.
  </CardFooter>
</Card>
{/if}
