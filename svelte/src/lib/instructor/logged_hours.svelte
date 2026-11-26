<script lang="ts">
	import { onMount } from 'svelte';
	import {
		Alert,
		Card,
		CardBody,
		CardHeader,
		CardTitle,
		Spinner,
		Table
	} from '@sveltestrap/sveltestrap';
	import { get } from '$lib/api.ts';
	import FetchError from '../fetch_error.svelte';

	interface LoggedHoursEntry {
		timestamp: string;
		class_name: string;
		class_date?: string;
		hours?: string;
		clearances?: string;
		tools?: string;
		students_passed?: string;
		volunteer?: string;
		event_id?: string;
	}

	export let email: string;

	let promise: Promise<{ logs: LoggedHoursEntry[] }> = Promise.resolve({ logs: [] });

	onMount(() => {
		promise = get('/instructor/logged_hours?email=' + encodeURIComponent(email));
	});

	function fmt_timestamp(ts: string | null | undefined): string {
		if (!ts) {
			return '';
		}
		return new Date(ts).toLocaleString('en-US', { timeZone: 'America/New_York' });
	}

	function clearances_tools(log: LoggedHoursEntry): string {
		return [log.clearances, log.tools].filter(Boolean).join(' / ');
	}
</script>

<Card class="my-3">
	<CardHeader>
		<CardTitle>Logged Hours</CardTitle>
	</CardHeader>
	<CardBody>
		<Alert color="info">
			This is a read-only view of your submitted instructor hours and clearance logs. To submit a
			new log, use the <strong>Submit Log</strong> button on the scheduled class in the Classes tab,
			or use the
			<a
				href="https://docs.google.com/forms/d/e/1FAIpQLScX3HbZJ1-Fm_XPufidvleu6iLWvMCASZ4rc8rPYcwu_G33gg/viewform"
				target="_blank">Log Form (Blank)</a
			>
			link at the top of this page.
		</Alert>

		{#await promise}
			<Spinner />
			<strong>Loading logged hours...</strong>
		{:then data}
			{#if data.logs.length === 0}
				<Alert color="secondary">No submitted hours or clearance logs found.</Alert>
			{:else}
				<Table responsive striped hover>
					<thead>
						<tr>
							<th>Submitted</th>
							<th>Class</th>
							<th>Class Date</th>
							<th>Hours</th>
							<th>Clearances / Tools</th>
							<th>Students Passed</th>
						</tr>
					</thead>
					<tbody>
						{#each data.logs as log}
							<tr>
								<td>{fmt_timestamp(log.timestamp)}</td>
								<td>{log.class_name || 'Unknown class'}</td>
								<td>{log.class_date || ''}</td>
								<td>{log.hours || ''}</td>
								<td>{clearances_tools(log)}</td>
								<td>{log.students_passed || ''}</td>
							</tr>
						{/each}
					</tbody>
				</Table>
			{/if}
		{:catch error}
			<FetchError {error} />
		{/await}
	</CardBody>
</Card>
