<script lang="ts">
  import { onMount } from 'svelte';
  import { Card, CardBody, CardHeader, CardTitle, Table, Spinner, ListGroup, ListGroupItem } from '@sveltestrap/sveltestrap';
  import { get } from '$lib/api';
import FetchError from '../fetch_error.svelte';

  let promise = new Promise(()=>{});
  onMount(() => {
    promise = get("/events/upcoming").then((data) => {
      for (let e of data.events) {
        e.attendees = get(`/events/attendees?id=${encodeURIComponent(e.id)}`);
      }
      return data;
    });
  });
</script>

<Card>
  <CardHeader>
    <CardTitle>Classes</CardTitle>
  </CardHeader>
  <CardBody>
  {#await promise}
      <Spinner/>
  {:then p}
    <div>
      As of {p.now}.
    </div>
    <p><strong>NOTE: Multi-day classes are only shown by their start date</strong></p>

    <Table id="schedule">
      <thead>
        <tr>
          <th>Event</th>
	  <th>Instructor</th>
          <th>Start Date</th>
          <th>Start Time</th>
          <th>End Date</th>
	  <th>End Time</th>
          <th>Attendees</th>
          <th>Capacity</th>
          <th>Reservation</th>
        </tr>
      </thead>
      <tbody>
        {#each p.events as event}
        <tr id="{event['id']}">
          <td>{event['name']}</td>
	  <td>{event['instructor']}</td>
          <td style="text-align: right">{event['start_date']}</td>
          <td style="text-align: right">{event['start_time']}</td>
          <td style="text-align: right">{event['end_date']}</td>
          <td style="text-align: right">{event['end_time']}</td>
          <td class="attendees">
          {#await event.attendees}
          Loading...
          {:then a}{a}
          {:catch error}{error}
          {/await}
          </td>
          <td>{event['capacity'] || ""}</td>
          <td>{event['registration'] ? 'open' : 'closed'}</td>
        </tr>
        {/each}
      </tbody>
    </Table>

  {/await}
  </CardBody>
</Card>
