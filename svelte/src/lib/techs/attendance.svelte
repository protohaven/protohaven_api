<script type="typescript" lang="ts">
import { onMount } from 'svelte';
import {
  Table, Dropdown, DropdownToggle, DropdownItem, DropdownMenu, Button, Row, Container, Col, Card,
  CardHeader, Badge, CardTitle, Modal, CardSubtitle, CardText, Icon, Tooltip, CardFooter, CardBody,
  Input, Spinner, FormGroup, Navbar, NavbarBrand, Nav, NavItem, Toast, ToastBody, ToastHeader,
  ListGroup, ListGroupItem
} from '@sveltestrap/sveltestrap';
import { get, post, isodate } from '$lib/api.ts';
import type { Tech, DisplayTech, SearchResult, ToastMessage, SortType, TechListData } from './types';
import FetchError from '../fetch_error.svelte';
import TechCard from './tech_card.svelte';

// Component props
export let visible: boolean;

const DEFAULT_DURATION=30;
const DEFAULT_TRAIL=1;

let promise = Promise.resolve([]);
let start_date = new Date();
let end_date = new Date(start_date);
start_date.setDate(start_date.getDate() - DEFAULT_DURATION - DEFAULT_TRAIL);
start_date = isodate(start_date);
end_date.setDate(end_date.getDate() - DEFAULT_TRAIL);
end_date = isodate(end_date);
function fetch_attendance() {
  promise = post('/techs/attendance_report', {start_date, end_date}).then((data) => {
    console.log(data);
    return data;
  });
}

</script>


{#if visible}
  <Card>
    <CardHeader>
      <CardTitle>Tech Attendance</CardTitle>
      <CardSubtitle>Compute on-time, callouts, no-shows etc. over a time window</CardSubtitle>
    </CardHeader>
    <CardBody>
      <Input type="date" placeholder="From Date" bind:value={start_date}/>
      <Input type="date" placeholder="To Date" bind:value={end_date}/>
      <Button on:click={fetch_attendance}>Generate Report</Button>
      {#await promise}
        <Spinner/> Loading...
      {:then p}
      {#if p && p.rows && p.rows.length > 0}
        <Table>
          <thead>
          {#each p.header as k}
            <th>{k}</th>
          {/each}
          </thead>
          <tbody>
          {#each p.rows as row}
            <tr>
              {#each row as cell}
              <td>{cell}</td>
              {/each}
            </tr>
          {/each}
          </tbody>
        </Table>
      {:else}
        No attendance data for interval
      {/if}
      {:catch error}
        <FetchError {error}/>
      {/await}
    </CardBody>
  </Card>

{/if}
