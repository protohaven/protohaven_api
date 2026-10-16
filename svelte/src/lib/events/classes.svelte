<script lang="ts">
	import { onMount } from 'svelte';
	import { Card, CardBody, CardHeader, CardTitle, Table, Spinner } from '@sveltestrap/sveltestrap';
	import { get } from '$lib/api';

	interface UpcomingEvent {
		id: string | number;
		name?: string;
		instructor?: string;
		start: Date;
		end: Date;
		attendees: Promise<unknown>;
		capacity?: string | number;
		registration?: boolean;
	}

	interface UpcomingData {
		now: string;
		events: UpcomingEvent[];
	}

	let promise: Promise<UpcomingData> = new Promise<UpcomingData>(() => {});
	onMount(() => {
		promise = get('/events/upcoming').then((data: UpcomingData) => {
			for (const e of data.events) {
				e.attendees = get(`/events/attendees?id=${encodeURIComponent(String(e.id))}`);
				e.start = new Date(e.start);
				e.end = new Date(e.end);
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
			<Spinner />
		{:then p}
			<div>
				As of {p.now}.
			</div>
			<p><strong>NOTE: Multi-day classes are only shown by their start date</strong></p>
			<p>
				Time zone: {Intl.DateTimeFormat().resolvedOptions().timeZone}
			</p>

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
						<tr id={String(event['id'])}>
							<td>{event['name']}</td>
							<td>{event['instructor']}</td>
							<td style="text-align: right">{event.start.toLocaleDateString()}</td>
							<td style="text-align: right">{event.start.toLocaleTimeString()}</td>
							<td style="text-align: right">{event.end.toLocaleDateString()}</td>
							<td style="text-align: right">{event.end.toLocaleTimeString()}</td>
							<td class="attendees">
								{#await event.attendees}
									Loading...
								{:then a}{a}
								{:catch error}{error}
								{/await}
							</td>
							<td>{event['capacity'] || ''}</td>
							<td>{event['registration'] ? 'open' : 'closed'}</td>
						</tr>
					{/each}
				</tbody>
			</Table>
		{/await}
	</CardBody>
</Card>

<style>
	tr:nth-child(even) {
		background-color: #ccc;
	}
</style>
