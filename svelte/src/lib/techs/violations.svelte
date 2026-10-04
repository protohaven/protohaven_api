<script lang="ts">
	import {
		Badge,
		Button,
		Card,
		CardBody,
		CardHeader,
		CardSubtitle,
		CardTitle,
		Col,
		FormGroup,
		Input,
		Label,
		ListGroup,
		ListGroupItem,
		Row,
		Spinner,
		Toast,
		ToastBody,
		ToastHeader
	} from '@sveltestrap/sveltestrap';
	import { get, post, as_datetimelocal, isodate } from '$lib/api.ts';
	import FetchError from '../fetch_error.svelte';

	export let visible;
	export let user = null;

	const WIKI_FEES_URL =
		'https://wiki.protohaven.org/books/policies/page/storage-policy#bkmrk-violations';

	let loaded = false;
	let violations_promise = Promise.resolve([]);
	let sections_promise = Promise.resolve([]);

	let reporter = '';
	let reporter_initialized = false;
	$: if (user && !reporter_initialized) {
		reporter = `${user.fullname} <${user.email}>`;
		reporter_initialized = true;
	}

	let search_term = '';
	let searching = false;
	let search_results = [];
	let selected_member = null;

	let tag_number = '';
	let onset = as_datetimelocal(new Date());
	let notes = '';
	let evidence = '';
	let custom_fee = '';
	let selected_sections = {};
	let fee_presets = [
		{ label: 'Cart / parking / board / sheet', amount: 5, selected: false },
		{ label: 'Table / locker / cage / rack', amount: 10, selected: false },
		{ label: 'Large project / rental room', amount: 15, selected: false }
	];

	let submitting = false;
	let close_state = {};
	let toast_msg = null;

	function refresh() {
		violations_promise = get('/techs/violations').then((data) => {
			loaded = true;
			return data;
		});
	}

	function refresh_sections() {
		sections_promise = get('/techs/violations/sections');
	}

	$: if (visible && !loaded) {
		refresh();
		refresh_sections();
	}

	function show_toast(color, title, msg) {
		toast_msg = { color, title, msg };
	}

	function search_member() {
		searching = true;
		search_results = [];
		post(`/neon_lookup?search=${encodeURIComponent(search_term)}`)
			.then((data) => {
				search_results = data || [];
				if (!search_results.length) {
					show_toast('info', 'Member search', 'No matching members found');
				}
			})
			.catch((err) => show_toast('danger', 'Member search failed', err.message))
			.finally(() => (searching = false));
	}

	function select_member(m) {
		selected_member = { neon_id: m.neon_id, name: m.name, email: m.email };
		search_results = [];
		search_term = `${m.name} <${m.email}>`;
	}

	function clear_member() {
		selected_member = null;
		search_term = '';
		search_results = [];
	}

	$: preset_total = fee_presets.filter((p) => p.selected).reduce((total, p) => total + p.amount, 0);
	$: daily_fee = preset_total + (Number(custom_fee) || 0);

	function submit_violation() {
		submitting = true;
		post('/techs/violations/open', {
			reporter: reporter || (user ? `${user.fullname} <${user.email}>` : ''),
			neon_id: selected_member ? selected_member.neon_id : null,
			tag_number,
			onset,
			sections: Object.keys(selected_sections).filter((id) => selected_sections[id]),
			notes,
			evidence: evidence
				.split(/[\n,]+/)
				.map((u) => u.trim())
				.filter(Boolean),
			daily_fee
		})
			.then(() => {
				show_toast('success', 'Violation opened', 'The violation was added to Airtable.');
				refresh();
				tag_number = '';
				notes = '';
				evidence = '';
				custom_fee = '';
				selected_sections = {};
				selected_member = null;
				search_term = '';
				fee_presets = fee_presets.map((p) => ({ ...p, selected: false }));
			})
			.catch((err) => show_toast('danger', 'Error opening violation', err.message))
			.finally(() => (submitting = false));
	}

	function begin_close(v) {
		close_state = {
			...close_state,
			[v.id]: {
				open: true,
				closer: user ? `${user.fullname} <${user.email}>` : '',
				close_date: isodate(new Date()),
				notes: '',
				fees_outstanding: false
			}
		};
	}

	function submit_close(v) {
		const c = close_state[v.id];
		post(`/techs/violations/${v.id}/close`, {
			closer: c.closer,
			close_date: c.close_date,
			notes: c.notes,
			fees_outstanding: c.fees_outstanding
		})
			.then(() => {
				show_toast('success', 'Violation closed', 'The closure was added to Airtable.');
				close_state = { ...close_state, [v.id]: { ...c, open: false } };
				refresh();
			})
			.catch((err) => show_toast('danger', 'Error closing violation', err.message));
	}
</script>

{#if visible}
	<Card>
		<CardHeader>
			<CardTitle>Policy Violations</CardTitle>
			<CardSubtitle
				>Open and close storage/policy violations without leaving the dashboard</CardSubtitle
			>
		</CardHeader>
		<CardBody>
			<Card class="mb-3">
				<CardHeader>
					<CardTitle>New Violation</CardTitle>
					<CardSubtitle
						>Assign a member by name, choose policy sections, and set the daily fee.</CardSubtitle
					>
				</CardHeader>
				<CardBody>
					<Row>
						<Col md="6">
							<FormGroup>
								<Label for="violation-member-search">Member</Label>
								<Input
									id="violation-member-search"
									type="text"
									bind:value={search_term}
									placeholder="Search by name or email"
									disabled={searching}
								/>
								<div class="d-flex gap-2 my-2">
									<Button
										on:click={search_member}
										disabled={searching || search_term === '' || !!selected_member}
									>
										Search
									</Button>
									{#if selected_member}
										<Button color="light" on:click={clear_member}>Clear</Button>
									{/if}
								</div>
								{#if selected_member}
									<div class="border rounded p-2">
										<strong>{selected_member.name}</strong><br />
										{selected_member.email}
									</div>
								{/if}
								{#if search_results.length}
									<ListGroup class="my-2">
										{#each search_results as r}
											<ListGroupItem action on:click={() => select_member(r)}>
												{r.name} — {r.email}
											</ListGroupItem>
										{/each}
									</ListGroup>
								{/if}
							</FormGroup>
							<FormGroup>
								<Label for="violation-tag-number">Tag Number</Label>
								<Input
									id="violation-tag-number"
									type="text"
									bind:value={tag_number}
									placeholder="Storage tag number, if applicable"
								/>
							</FormGroup>
							<FormGroup>
								<Label for="violation-reporter">Reporter</Label>
								<Input id="violation-reporter" type="text" bind:value={reporter} />
							</FormGroup>
							<FormGroup>
								<Label for="violation-onset">Onset</Label>
								<Input id="violation-onset" type="datetime-local" bind:value={onset} />
							</FormGroup>
						</Col>
						<Col md="6">
							<FormGroup>
								<Label>Relevant sections</Label>
								{#await sections_promise}
									<Spinner /> Loading sections...
								{:then sections}
									<div class="d-flex flex-wrap gap-2">
										{#each sections as s}
											<Button
												color={selected_sections[s.id] ? 'primary' : 'light'}
												on:click={() =>
													(selected_sections = {
														...selected_sections,
														[s.id]: !selected_sections[s.id]
													})}
											>
												{s.name}
											</Button>
										{/each}
									</div>
								{:catch error}
									<FetchError {error} />
								{/await}
							</FormGroup>
							<FormGroup>
								<Label for="violation-notes">Notes</Label>
								<Input
									id="violation-notes"
									type="textarea"
									bind:value={notes}
									placeholder="Location, storage type, or other details. Be professional and considerate."
								/>
							</FormGroup>
							<FormGroup>
								<Label for="violation-evidence">Evidence URLs</Label>
								<Input
									id="violation-evidence"
									type="textarea"
									bind:value={evidence}
									placeholder="One image/evidence URL per line"
								/>
							</FormGroup>
						</Col>
					</Row>
					<Row>
						<Col md="6">
							<FormGroup>
								<Label>Usual daily fees</Label>
								<div class="d-flex flex-wrap gap-2">
									{#each fee_presets as p, i}
										<Button
											color={p.selected ? 'primary' : 'light'}
											on:click={() =>
												(fee_presets = fee_presets.map((x, j) =>
													j === i ? { ...x, selected: !x.selected } : x
												))}
										>
											{p.label} (${p.amount})
										</Button>
									{/each}
								</div>
							</FormGroup>
						</Col>
						<Col md="6">
							<FormGroup>
								<Label for="violation-custom-fee">Custom fee amount</Label>
								<Input
									id="violation-custom-fee"
									type="number"
									min="0"
									step="0.01"
									bind:value={custom_fee}
								/>
								<div class="my-2">
									<strong>Daily fee: ${daily_fee.toFixed(2)}</strong>
								</div>
								<a href={WIKI_FEES_URL} target="_blank">Storage fee guide (wiki)</a>
							</FormGroup>
						</Col>
					</Row>
					<Button color="primary" on:click={submit_violation} disabled={submitting}>
						{submitting ? 'Submitting...' : 'Open Violation'}
					</Button>
				</CardBody>
			</Card>

			<h2>Violations</h2>
			{#await violations_promise}
				<Spinner /> Loading violations...
			{:then violations}
				{#if !violations.length}
					<p>No violations found.</p>
				{/if}
				{#each violations as v}
					<Card class="my-2" color={v.closed ? null : 'warning'}>
						<CardHeader>
							<div class="d-flex justify-content-between align-items-start">
								<div>
									<CardTitle>
										Violation {v.instance ? `#${v.instance}` : ''}
										{v.tag_number ? ` / Tag #${v.tag_number}` : ''}
									</CardTitle>
									<CardSubtitle>Opened {new Date(v.onset).toLocaleString()}</CardSubtitle>
								</div>
								{#if v.closed}
									<Badge color="success">Closed</Badge>
								{:else}
									<Badge color="danger">Open</Badge>
								{/if}
							</div>
						</CardHeader>
						<CardBody>
							<p>
								<strong>Member:</strong>
								{v.suspect_name || 'Unknown'}
								{#if v.suspect_email}
									({v.suspect_email}){/if}
							</p>
							<p><strong>Reporter:</strong> {v.reporter || 'Unknown'}</p>
							<p><strong>Sections:</strong> {v.sections.join(', ') || 'None'}</p>
							<p><strong>Notes:</strong> {v.notes || 'None'}</p>
							{#if v.evidence.length}
								<p>
									<strong>Evidence:</strong>
									{#each v.evidence as url}
										<a class="d-block" href={url} target="_blank">{url}</a>
									{/each}
								</p>
							{/if}
							<p>
								<strong>Daily fee:</strong> ${v.daily_fee ?? 0} / day ·
								<strong>Accrued:</strong> ${v.accrued ?? 0} ·
								<strong>Unpaid fees:</strong> ${v.unpaid_fees ?? 0}
							</p>
							{#if v.closed}
								<p>
									<strong>Closed:</strong>
									{v.close_date ? new Date(v.close_date).toLocaleDateString() : 'Unknown'}
								</p>
							{:else if close_state[v.id] && close_state[v.id].open}
								<Row>
									<Col md="3">
										<Input
											type="text"
											bind:value={close_state[v.id].closer}
											placeholder="Name and email"
										/>
									</Col>
									<Col md="3">
										<Input type="date" bind:value={close_state[v.id].close_date} />
									</Col>
									<Col md="4">
										<Input
											type="textarea"
											bind:value={close_state[v.id].notes}
											placeholder="How/why was the violation closed?"
										/>
									</Col>
									<Col md="2">
										<Input type="checkbox" bind:checked={close_state[v.id].fees_outstanding} />
										Fees outstanding?
									</Col>
								</Row>
								<Button class="mt-2" color="success" on:click={() => submit_close(v)}>
									Submit closure
								</Button>
							{:else}
								<Button color="success" on:click={() => begin_close(v)}>Close Violation</Button>
							{/if}
						</CardBody>
					</Card>
				{/each}
			{:catch error}
				<FetchError {error} />
			{/await}
		</CardBody>
	</Card>
	<Toast
		class="me-1"
		style="z-index: 10000; position:fixed; bottom: 2vh; right: 2vh;"
		autohide
		isOpen={toast_msg}
		on:close={() => (toast_msg = null)}
	>
		<ToastHeader icon={toast_msg.color}>{toast_msg.title}</ToastHeader>
		<ToastBody>{toast_msg.msg}</ToastBody>
	</Toast>
{/if}
