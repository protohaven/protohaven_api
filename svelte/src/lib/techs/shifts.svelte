<script type="typescript" lang="ts">
	import {
		Label,
		Button,
		Card,
		CardHeader,
		CardTitle,
		CardFooter,
		CardBody,
		Input,
		Spinner,
		FormGroup
	} from '@sveltestrap/sveltestrap';
	import Editor from './forecast_override.svelte';
	import FetchError from '../fetch_error.svelte';
	import { get, isodate } from '$lib/api.ts';
	import { days_between, isToday } from '$lib/dates';

	interface UserInfo {
		fullname?: string;
		email?: string;
		[key: string]: unknown;
	}

	interface ForecastOverrideInfo {
		id?: string;
		orig?: string[];
		editor?: string;
	}

	interface ShiftPeriod {
		id?: string;
		color?: string;
		ovr?: ForecastOverrideInfo | null;
		people: string[];
	}

	interface CalendarDay {
		filler?: boolean;
		date: string;
		AM: ShiftPeriod;
		PM: ShiftPeriod;
	}

	interface ForecastEdit {
		ap: string;
		date: string;
		techs: string[];
		id?: string;
		orig?: string[];
		editor?: string;
		fullname?: string;
		email?: string;
		[key: string]: unknown;
	}

	export let user: UserInfo | null = null;
	export let visible: boolean;

	const DEFAULT_DURATION = 14;
	const DEFAULT_TRAIL = 3;

	let start_date: string;
	let end_date: string;
	{
		const start = new Date();
		const end = new Date(start);
		start.setDate(start.getDate() - DEFAULT_TRAIL);
		end.setDate(end.getDate() + DEFAULT_DURATION);
		start_date = isodate(start);
		end_date = isodate(end);
	}

	let loaded = false;
	let promise: Promise<CalendarDay[]> = new Promise(() => {});
	function refresh() {
		const diff_days = days_between(start_date, end_date) + 1; // Inclusive
		promise = get(`/techs/forecast?date=${isodate(start_date)}&days=${diff_days}`).then((data) => {
			loaded = true;

			// Left pad data until we hit a Sunday
			if (!data.calendar_view) {
				return [];
			}
			const cal = data.calendar_view;
			let d = new Date(cal[0].date);
			while (d.getUTCDay() !== 0) {
				d.setDate(d.getDate() - 1);
				cal.unshift({ date: isodate(d), filler: true, AM: { people: [] }, PM: { people: [] } });
			}
			d = new Date(cal[cal.length - 1].date);
			while (d.getUTCDay() !== 6) {
				d.setDate(d.getDate() + 1);
				cal.push({ date: isodate(d), filler: true, AM: { people: [] }, PM: { people: [] } });
			}
			return cal;
		});
	}
	function date_changed(was_start: boolean) {
		console.log('date_changed');
		let fix: number | null = null;
		let start = new Date(start_date);
		let end = new Date(end_date);
		if (!end || end < start) {
			fix = DEFAULT_DURATION;
		} else if (days_between(start_date, end_date) > 60) {
			fix = 60;
		}

		if (fix) {
			console.log('fix', fix);
			if (was_start) {
				const d = new Date(start_date);
				d.setDate(d.getDate() + fix);
				end_date = isodate(d);
			} else {
				const d = new Date(end_date);
				d.setDate(d.getDate() - fix);
				start_date = isodate(d);
			}
		}
		refresh();
	}
	$: {
		if (visible && !loaded) {
			refresh();
		}
	}

	let edit: ForecastEdit | null = null;
	const shift_periods: ('AM' | 'PM')[] = ['AM', 'PM'];

	function start_edit(s: CalendarDay, ap: 'AM' | 'PM') {
		console.log(s, ap);
		let e: ForecastEdit = { ap: ap, date: s.date, techs: s[ap].people, ...(user ?? {}) };
		if (s[ap].ovr) {
			e = { ...e, id: s[ap].ovr.id, orig: s[ap].ovr.orig, editor: s[ap].ovr.editor };
		} else {
			e = { ...e, orig: [...s[ap].people] };
		}
		edit = e;
	}
</script>

{#if visible}
	<Card>
		<CardHeader>
			<CardTitle>Calendar</CardTitle>
			<p>An editable forecast of upcoming shifts.</p>
		</CardHeader>
		<CardBody>
			<FormGroup>
				<Label>Start Date</Label>
				<Input type="date" bind:value={start_date} on:change={() => date_changed(true)} />
			</FormGroup>
			<FormGroup>
				<Label>End Date</Label>
				<Input type="date" bind:value={end_date} on:change={() => date_changed(false)} />
			</FormGroup>

			{#await promise}
				<Spinner />Loading...
			{:then p}
				<div class="calendar">
					<div class="header">Sun</div>
					<div class="header">Mon</div>
					<div class="header">Tue</div>
					<div class="header">Wed</div>
					<div class="header">Thu</div>
					<div class="header">Fri</div>
					<div class="header">Sat</div>
					{#each p as v}
						{#if v.filler}
							<div class="filler"></div>
						{:else}
							<Card>
								<span class={'day' + (isToday(v.date) ? ' today' : '')}>
									<div>{v.date}</div>
									<div class="my-2">
										{#each shift_periods as ap}
											<div>
												{#if v[ap].ovr}*{/if}{ap}
											</div>
											<Button
												id={v[ap].id}
												class="p-2 mx-2"
												color={v[ap].color}
												on:click={() => start_edit(v, ap)}
											>
												{#if v[ap].people.length === 0}
													Nobody on shift!
												{:else}
													{#each v[ap].people as ppl}<div class="my-2">{ppl}</div>{/each}
												{/if}
											</Button>
										{/each}
									</div>
								</span>
							</Card>
						{/if}
					{/each}
				</div>
			{:catch error}
				<FetchError {error} />
			{/await}
		</CardBody>
		<CardFooter>
			<p>
				Legend:
				<Button color="success">3+ Techs</Button>
				<Button color="info">2 Techs</Button>
				<Button color="warning">1 Tech</Button>
				<Button color="danger">0 Techs</Button>
			</p>
			<p><em>* indicates overridden shift info</em></p>
		</CardFooter>
	</Card>
{/if}

<Editor {edit} on_update={refresh} />

<style>
	.calendar {
		display: grid;
		gap: 5px;
		grid-template-columns: repeat(7, 1fr);
		@media (max-width: 920px) {
			grid-template-columns: repeat(3, 1fr);
		}
	}
	.today {
		background-color: #eeeeff;
		font-weight: bold;
	}
	.header {
		text-align: center;
		@media (max-width: 920px) {
			display: none;
		}
	}
	.filler {
		background-color: #eee;
	}
</style>
