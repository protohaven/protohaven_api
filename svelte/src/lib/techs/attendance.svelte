<script type="typescript" lang="ts">
	import {
		Table,
		Button,
		Card,
		CardHeader,
		CardTitle,
		CardSubtitle,
		CardBody,
		Input,
		Spinner
	} from '@sveltestrap/sveltestrap';
	import { post, isodate } from '$lib/api.ts';
	import FetchError from '../fetch_error.svelte';

	// Component props
	export let visible: boolean;

	const DEFAULT_DURATION = 30;
	const DEFAULT_TRAIL = 1;

	interface AttendanceReport {
		header: string[];
		rows: (string | number)[][];
	}

	let promise: Promise<AttendanceReport> = Promise.resolve({ header: [], rows: [] });
	let start_date: string;
	let end_date: string;
	{
		const start = new Date();
		const end = new Date(start);
		start.setDate(start.getDate() - DEFAULT_DURATION - DEFAULT_TRAIL);
		end.setDate(end.getDate() - DEFAULT_TRAIL);
		start_date = isodate(start);
		end_date = isodate(end);
	}
	function fetch_attendance() {
		promise = post('/techs/attendance_report', { start_date, end_date }).then((data) => {
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
			<Input type="date" placeholder="From Date" bind:value={start_date} />
			<Input type="date" placeholder="To Date" bind:value={end_date} />
			<Button on:click={fetch_attendance}>Generate Report</Button>
			{#await promise}
				<Spinner /> Loading...
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
				<FetchError {error} />
			{/await}
		</CardBody>
	</Card>
{/if}
