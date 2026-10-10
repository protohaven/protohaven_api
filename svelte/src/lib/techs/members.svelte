<script type="typescript" lang="ts">
	import {
		FormGroup,
		Label,
		Accordion,
		AccordionItem,
		ListGroup,
		ListGroupItem,
		Button,
		Card,
		CardHeader,
		CardTitle,
		CardSubtitle,
		CardBody,
		Input,
		Spinner,
		Toast,
		ToastBody,
		ToastHeader
	} from '@sveltestrap/sveltestrap';

	import FetchError from '../fetch_error.svelte';
	import { get, isodate, post } from '$lib/api.ts';
	import { calculate_day_of_week_stats, DAY_NAMES } from './signin_stats';

	type SearchResult = {
		name: string;
		email: string;
	};

	type ToastMsg = {
		color: string;
		title: string;
		msg: string;
	} | null;

	type SigninRecord = {
		email: string;
		name: string;
		member: boolean;
		status: string;
		clearances: string[];
		violations: string[];
		created: Date;
	};

	type GroupedSignin = SigninRecord & {
		timestamps: Set<string>;
	};

	let start_date = isodate(new Date());
	let end_date = isodate(new Date());

	export let visible: boolean = false;
	let search_term = '';
	let search_results: SearchResult[] = [];
	let searching = false;
	let selected_member: SearchResult | null = null;
	let promise: Promise<GroupedSignin[]> = Promise.resolve([]);
	let loaded = false;
	let toast_msg: ToastMsg = null;

	// Day of week statistics
	let day_of_week_stats = {
		Sunday: 0,
		Monday: 0,
		Tuesday: 0,
		Wednesday: 0,
		Thursday: 0,
		Friday: 0,
		Saturday: 0
	};
	let total_signins = 0;

	// Debounce function for search
	function debounce(func: (...args: unknown[]) => void, wait: number) {
		let timeout: ReturnType<typeof setTimeout> | undefined;
		return function executedFunction(...args: unknown[]) {
			const later = () => {
				clearTimeout(timeout);
				func(...args);
			};
			clearTimeout(timeout);
			timeout = setTimeout(later, wait);
		};
	}

	const debouncedSearch = debounce(() => {
		if (!search_term.trim()) {
			search_results = [];
			return;
		}

		searching = true;
		post(`/neon_lookup?search=${encodeURIComponent(search_term)}`, undefined)
			.then((results) => {
				search_results = results;
			})
			.catch((err) => {
				console.error('Search failed:', err);
				search_results = [];
				toast_msg = {
					color: 'danger',
					msg: 'Failed to search Neon accounts',
					title: 'Search Error'
				};
			})
			.finally(() => {
				searching = false;
			});
	}, 300);

	function search_neon_accounts() {
		debouncedSearch();
	}

	function refresh() {
		const start = isodate(start_date);
		const end = isodate(end_date);
		promise = get(`/techs/members?start=${start}&end=${end}`).then((data: SigninRecord[]) => {
			loaded = true;
			let by_email_and_day: Record<string, GroupedSignin> = {};
			for (let d of data) {
				d.created = new Date(d.created);
				let dstr = isodate(d.created);
				const key = [d.email, dstr].join(',');
				if (!by_email_and_day[key]) {
					by_email_and_day[key] = { ...d, timestamps: new Set<string>() };
				}
				by_email_and_day[key].timestamps.add(d.created.toLocaleTimeString());
			}
			let results: GroupedSignin[] = Object.values(by_email_and_day);
			// Sort descending, newest on top
			results.sort((a, b) => b.created.getTime() - a.created.getTime());

			// Filter by selected member if one is selected
			if (selected_member) {
				const member = selected_member;
				results = results.filter((r) => r.email === member.email);
				// Calculate day of week statistics for selected member
				calculateDayOfWeekStats(data.filter((d) => d.email === member.email));
			} else {
				// Reset statistics when no member is selected
				resetDayOfWeekStats();
			}

			return results;
		});
	}

	function calculateDayOfWeekStats(memberSignins: SigninRecord[]) {
		const { stats, total_signins: total } = calculate_day_of_week_stats(memberSignins);
		day_of_week_stats = stats;
		total_signins = total;
	}

	function resetDayOfWeekStats() {
		day_of_week_stats = {
			Sunday: 0,
			Monday: 0,
			Tuesday: 0,
			Wednesday: 0,
			Thursday: 0,
			Friday: 0,
			Saturday: 0
		};
		total_signins = 0;
	}

	function on_search_term_edit() {
		if (search_term !== `${selected_member?.name} (${selected_member?.email})`) {
			search_neon_accounts();
		} else {
			search_results = [];
			selected_member = null;
		}
	}

	function clear_selection() {
		selected_member = null;
		search_term = '';
		search_results = [];
		resetDayOfWeekStats();
		refresh();
	}

	$: {
		if (visible && !loaded) {
			refresh();
		}
	}
</script>

{#if visible}
	<Card>
		<CardHeader>
			<CardTitle>Member Check</CardTitle>
			<CardSubtitle>Today's sign-ins, including membership state and clearances</CardSubtitle>
		</CardHeader>
		<CardBody>
			<div class="row">
				<div class="col-md-6">
					<FormGroup>
						<Label>Start Date</Label>
						<Input type="date" bind:value={start_date} on:change={refresh} />
					</FormGroup>
				</div>
				<div class="col-md-6">
					<FormGroup>
						<Label>End Date</Label>
						<Input type="date" bind:value={end_date} on:change={refresh} />
					</FormGroup>
				</div>
			</div>

			<FormGroup>
				<Label>Search Member</Label>
				<div class="position-relative">
					<div class="d-flex align-items-center">
						<Input
							type="text"
							bind:value={search_term}
							on:keydown={on_search_term_edit}
							placeholder="Search by name or email"
							aria-label="Search members by name or email"
						/>
						{#if searching}
							<Spinner size="sm" class="ms-2" />
						{/if}
						{#if selected_member}
							<Button color="secondary" size="sm" class="ms-2" on:click={clear_selection}>
								Clear
							</Button>
						{/if}
					</div>

					{#if search_results.length > 0}
						<div
							class="position-absolute bg-white border rounded shadow mt-1"
							style="z-index: 1000; width: 100%; max-height: 300px; overflow-y: auto;"
						>
							<ListGroup flush>
								{#each search_results as result}
									<ListGroupItem
										tag="button"
										action
										on:click={() => {
											selected_member = result;
											search_term = `${selected_member.name} (${selected_member.email})`;
											search_results = [];
											refresh();
										}}
										class="text-start"
									>
										{result.name} ({result.email})
									</ListGroupItem>
								{/each}
							</ListGroup>
						</div>
					{/if}
				</div>
				<small class="form-text text-muted">
					{#if selected_member}
						Showing sign-in history for {selected_member.name} only
					{:else}
						Showing all members who signed in on selected date
					{/if}
				</small>
			</FormGroup>

			{#if selected_member && total_signins > 0}
				<div class="mt-4">
					<h5>Sign-in Frequency for {selected_member.name}</h5>
					<p class="text-muted">
						Showing distinct days signed in for each day of the week
						{#if start_date !== end_date}
							from {new Date(start_date).toLocaleDateString()} to {new Date(
								end_date
							).toLocaleDateString()}
						{:else}
							on {new Date(start_date).toLocaleDateString()}
						{/if}
					</p>

					<div class="table-responsive">
						<table class="table table-bordered table-sm">
							<thead>
								<tr>
									<th>Day of Week</th>
									<th>Distinct Days Signed In</th>
								</tr>
							</thead>
							<tbody>
								{#each Object.entries(day_of_week_stats) as [day, count]}
									<tr>
										<td>{day}</td>
										<td>
											{#if count > 0}
												<strong>{count}</strong>
											{:else}
												<span class="text-muted">0</span>
											{/if}
										</td>
									</tr>
								{/each}
								<tr class="table-secondary">
									<td><strong>Total Sign-ins</strong></td>
									<td><strong>{total_signins}</strong></td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>
			{/if}

			{#await promise}
				<Spinner />Loading...
			{:then p}
				<ListGroup>
					{#each p as r}
						<ListGroupItem>
							<p>
								<strong
									>{r.email}{#if r.name}&nbsp;({r.name}){/if}</strong
								>
								{#if isodate(r.created) != isodate(new Date())}
									{DAY_NAMES[r.created.getDay()]} {isodate(r.created)}
								{/if}
								{r.created.toLocaleTimeString()} -
								{#if !r.member}
									Guest
								{:else}
									Member (<span
										style="{r.status !== 'Active' ? 'background-color: yellow;' : null}}"
										>{r.status}</span
									>)
								{/if}
							</p>
							{#if r.timestamps.size > 1}
								<p>All event timestamps: {Array.from(r.timestamps).join(', ')}</p>
							{/if}
							{#if !r.clearances.length && !r.violations.length}
								<p>No clearances, no violations</p>
							{:else}
								<Accordion>
									{#if r.clearances.length}
										<AccordionItem header={r.clearances.length + ' clearance(s)'}>
											<ListGroup>
												{#each r.clearances as c}
													<ListGroupItem>{c}</ListGroupItem>
												{/each}
											</ListGroup>
										</AccordionItem>
									{/if}
									{#if r.violations.length}
										<AccordionItem>
											<p
												class="m-0"
												slot="header"
												style={r.violations.length ? 'background-color: yellow;' : null}
											>
												{r.violations.length + ' violation(s)'}
											</p>
											<ListGroup>
												{#each r.violations as v}
													<ListGroupItem>{v}</ListGroupItem>
												{/each}
											</ListGroup>
										</AccordionItem>
									{/if}
								</Accordion>
							{/if}
						</ListGroupItem>
					{/each}
				</ListGroup>
			{:catch error}
				<FetchError {error} />
			{/await}

			<Toast
				class="me-1"
				style="z-index: 10000; position:fixed; bottom: 2vh; right: 2vh;"
				autohide
				isOpen={toast_msg !== null}
				on:close={() => (toast_msg = null)}
			>
				<ToastHeader icon={toast_msg?.color}>{toast_msg?.title}</ToastHeader>
				<ToastBody>{toast_msg?.msg}</ToastBody>
			</Toast>
		</CardBody>
	</Card>
{/if}
