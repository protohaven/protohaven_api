<script type="typescript">

import {onMount} from 'svelte';
import { Table, Badge, Popover, Card, CardHeader, CardTitle, CardText, CardBody, Spinner, Navbar, NavbarBrand, Nav, NavItem, } from '@sveltestrap/sveltestrap';
import FetchError from '../fetch_error.svelte';
import { open_ws } from '../api';

export let visible;

let loaded = false;
let loading = false;
let total = 0;
let index = 0;

let categories = [];
let categorized = {};
function refresh() {
  categories=["Errors"];
  categorized={"Errors": []};
  loading = true;
  const socket = open_ws('/staff/ops_summary');
  socket.onmessage = (m) => {
    console.log(m);
    let item = JSON.parse(m.data);
    total = item.total;
    index = item.index;
    if (!categorized[item.category]) {
      categorized[item.category] = [];
      categories.push(item.category);
      categories.sort();
      categories = categories;
    }
    categorized[item.category].push(item);
    categorized = categorized
  };
  socket.onerror = (error) => {
    // Ignore normal closure errors
    if (!error.message) {
      return;
    }
    console.error('WebSocket error:', error);
    alert(`WebSocket error: ${error.message || 'Connection failed'}`);
  };
  socket.onclose = () => {
    loading = false;
    loaded = true;
  };
}
$: {
  if (visible && !loaded) {
    refresh();
  }
}
</script>

{#if visible}
<Card>
<CardBody>
  <CardTitle>Ops Report</CardTitle>
  <p>For instantaneous operational state of the shop.</p>
    {#if loading}
      <Spinner/><em>Loading {index}/{total}...</em>
    {:else}
      <em>Loading complete.</em>
    {/if}
    <Table bordered>
      <thead>
        <tr>
        <th>Metric</th>
        <th>Value</th>
        <th>Target</th>
        <th>Source</th>
        <th>Timescale</th>
        </tr>
      </thead>
      <tbody>
      {#each categories as cat}
        <tr><th scope="row">{cat.toUpperCase()}</th></tr>
        {#each categorized[cat] as d}
        <tr>
          <td>{d.label}</td>
          {#if d.error }
            <td><Badge color="danger" id={d.label.replace(/[^a-zA-Z]/g, "")}>error</Badge>
            <Popover
                trigger="hover"
                placement="right"
                target={d.label.replace(/[^a-zA-Z]/g, "")}
                title="Exception">
                {d.error}
              </Popover>
            </td>
          {:else}
            <td style={"background-color: " + ((d.color == "warning")?"yellow":"none") + ";"}>{d.value}</td>
          {/if}
          <td>{d.target}</td>
          <td><a href={d.url}>{d.source}</a></td>
          <td>{d.timescale}</td>
        </tr>
        {/each}
      {/each}
      </tbody>
    </Table>
</CardBody>
</Card>
{/if}
