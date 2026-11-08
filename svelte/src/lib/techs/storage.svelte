<script type="typescript" lang="ts">
	import {
		Badge,
		Toast,
		Popover,
		ToastHeader,
		ToastBody,
		Dropdown,
		DropdownToggle,
		DropdownMenu,
		DropdownItem,
		Table,
		ListGroup,
		ListGroupItem,
		Button,
		Card,
		CardHeader,
		CardTitle,
		CardSubtitle,
		CardBody,
		Input,
		Spinner
	} from '@sveltestrap/sveltestrap';

	import FetchError from '../fetch_error.svelte';
	import { post, open_ws } from '$lib/api.ts';

	export let visible: boolean;
	let loaded = false;
	let search = '';
	let searching = false;

	interface MemberSearchResult {
		display: string;
	}

	let promise: Promise<MemberSearchResult[]> = new Promise((r) => {
		r([]);
	});
	function search_member() {
		searching = true;
		promise = post(`/neon_lookup?search=${encodeURIComponent(search)}`, {}).finally(
			() => (searching = false)
		);
	}

	let fetching = false;

	interface ToastMessage {
		color: string;
		title: string;
		msg: string;
	}

	let toast_msg: ToastMessage | null = null;

	interface Sub {
		customer: string;
		plan: string;
		membership_status: string;
		start_date: string;
		storage_type: string;
		storage_id: string;
		storage_detail: string;
		id: string | number;
		email?: string;
		unpaid: unknown[];
		status?: string;
		editable?: boolean;
		note?: string;
	}

	let subs: Sub[] = [];
	let includes_email = false;
	let subs_sorted: Sub[] = [];
	let sort_type = 'name';
	$: {
		if (sort_type === 'name') {
			subs_sorted = [...subs].sort((a, b) =>
				a.customer.toLowerCase().localeCompare(b.customer.toLowerCase())
			);
		} else if (sort_type === 'plan') {
			subs_sorted = [...subs].sort((a, b) =>
				a.plan.toLowerCase().localeCompare(b.plan.toLowerCase())
			);
		} else if (sort_type === 'memstatus') {
			subs_sorted = [...subs].sort((a, b) =>
				a.membership_status.toLowerCase().localeCompare(b.membership_status.toLowerCase())
			);
		} else if (sort_type === 'startdate') {
			subs_sorted = [...subs].sort((a, b) => a.start_date.localeCompare(b.start_date));
		} else if (sort_type === 'type') {
			subs_sorted = [...subs].sort((a, b) => a.storage_type.localeCompare(b.storage_type));
		} else if (sort_type === 'idnum') {
			subs_sorted = [...subs].sort((a, b) => a.id.toString().localeCompare(b.id.toString()));
		} else if (sort_type === 'detail') {
			subs_sorted = [...subs].sort((a, b) =>
				a.storage_detail.toLowerCase().localeCompare(b.storage_detail.toLowerCase())
			);
		}
	}

	let sub_fetch_status = '';
	function get_subs() {
		fetching = true;
		sub_fetch_status = '';
		console.log('get_subs');
		const socket = open_ws('/techs/storage_subscriptions');
		socket.addEventListener('close', (event) => {
			console.log(event);
			fetching = false;
			loaded = true;
		});
		subs = [];
		includes_email = false;
		socket.addEventListener('message', (event) => {
			let d = JSON.parse(event.data);
			if (d.error) {
				alert(d.error);
				return;
			}
			if (d.log_info) {
				sub_fetch_status = d.log_info;
				console.log(sub_fetch_status);
				return;
			}
			includes_email = includes_email || Boolean(d.email);
			let parsed: Record<string, unknown> = {};
			try {
				parsed = JSON.parse(d['note']) || {};
				console.log('Parsed', parsed);
			} catch (e) {
				parsed = {};
				console.warn('Failed parsing note', d, e);
			}
			d['storage_type'] = parsed['storage_type'] || 'Unknown';
			d['storage_id'] = parsed['storage_id'] || 'Unknown';
			d['storage_detail'] = parsed['storage_detail'];
			if (d['storage_detail'] === undefined) {
				d['storage_detail'] = d['note'] || '';
			}
			d['editable'] = d['plan'] !== 'Non-Square Agreement';
			subs.push(d);
			subs = subs;
		});
	}

	let sub_note_editing = false;
	let editing_sub_id: string | number | null = null;
	let draft_storage_type = 'Unknown';
	let draft_storage_id = 'Unknown';
	let draft_storage_detail = '';

	function start_edit(sub: Sub) {
		draft_storage_type = sub.storage_type;
		draft_storage_id = sub.storage_id;
		draft_storage_detail = sub.storage_detail;
		editing_sub_id = sub.id;
	}

	function cancel_edit() {
		editing_sub_id = null;
	}

	function set_draft_type(typ: string) {
		draft_storage_type = typ;
	}

	function save_edit() {
		if (editing_sub_id === null) {
			return;
		}
		const sub = subs.find((s) => s.id === editing_sub_id);
		if (!sub) {
			cancel_edit();
			return;
		}
		sub.storage_type = draft_storage_type;
		sub.storage_id = draft_storage_id;
		sub.storage_detail = draft_storage_detail;
		subs_sorted = subs_sorted; // Trigger repaint
		editing_sub_id = null;
		update_sub_note(sub);
	}
	function update_sub_note(sub: Sub) {
		sub.note = JSON.stringify({
			storage_type: sub.storage_type.trim(),
			storage_id: sub.storage_id.trim(),
			storage_detail: sub.storage_detail.trim()
		});
		console.log(`Setting sub ${sub.id} note: ${sub.note}`);
		sub_note_editing = true;
		post(`/techs/storage_subscriptions/${sub.id}/note`, { note: sub.note })
			.then((result) => {
				console.log(result);
				let msg = `${sub.customer} subscription notes updated`;
				toast_msg = { color: 'success', msg, title: 'Edit Success' };
				//get_subs();
			})
			.catch((err) => {
				console.error(err);
				toast_msg = {
					color: 'danger',
					msg: 'See console for details',
					title: 'Error updating subscription notes'
				};
			})
			.finally(() => (sub_note_editing = false));
	}

	$: {
		if (visible && !loaded) {
			get_subs();
		}
	}
</script>

{#if visible}
	<Card>
		<CardHeader>
			<CardTitle>Storage Violations</CardTitle>
			<CardSubtitle>Open, close, and view storage violations</CardSubtitle>
		</CardHeader>
		<CardBody>
			<ListGroup>
				<ListGroupItem
					><a
						href="https://protohaven.org/wiki/shoptechs/start#%F0%9F%93%A6_storage_%F0%9F%93%A6"
						target="_blank">Shop Tech Central: Storage</a
					></ListGroupItem
				>
				<ListGroupItem
					><a href="https://protohaven.org/violations" target="_blank">Active Violations</a
					></ListGroupItem
				>
				<ListGroupItem
					><a href="https://airtable.com/apppMbG0r1ZrluVMv/pag7q4CIgngxTpvw5/form" target="_blank"
						>Open a Violation</a
					></ListGroupItem
				>
				<ListGroupItem
					><a href="https://airtable.com/apppMbG0r1ZrluVMv/pagVSwa7QQ0sOOaEb/form" target="_blank"
						>Close a Violation</a
					></ListGroupItem
				>
			</ListGroup>
			<strong>Search for member neon ID:</strong>

			<Input type="text" bind:value={search} disabled={searching} />
			<Button on:click={search_member} disabled={searching || search === ''}>Search</Button>
			{#await promise}
				<Spinner /> Searching...
			{:then p}
				<ListGroup>
					{#each p as r}
						<ListGroupItem>{r.display}</ListGroupItem>
					{/each}
				</ListGroup>
			{:catch error}
				<FetchError {error} />
			{/await}
		</CardBody>
	</Card>

	<Card class="my-3">
		<CardHeader>
			<CardTitle>Storage Subscriptions</CardTitle>
			<CardSubtitle>View active subscriptions and add details*</CardSubtitle>
		</CardHeader>
		<CardBody>
			<div class="my-2">
				<em
					>*Non-Square storage agreements are editable <a
						href="https://airtable.com/appZIwlIgaq1Ps28Y/tblFoG5HKnRfuZsD7/viw3tzhfEh5trfBuH?blocks=hide"
						target="_blank">on Airtable</a
					></em
				>
			</div>
			{#if sub_note_editing}
				<Spinner /> {sub_fetch_status}
			{/if}
			{#if fetching}
				<Spinner /> Loading storage subscriptions... this may take up to a minute
			{/if}
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
			<Dropdown>
				<DropdownToggle color="secondary" caret>Sort</DropdownToggle>
				<DropdownMenu>
					<DropdownItem on:click={() => (sort_type = 'name')}>By Name</DropdownItem>
					<DropdownItem on:click={() => (sort_type = 'plan')}
						>By Plan (subscription name in Square)</DropdownItem
					>
					<DropdownItem on:click={() => (sort_type = 'memstatus')}
						>By Membership Status</DropdownItem
					>
					<DropdownItem on:click={() => (sort_type = 'startdate')}>By Start Date</DropdownItem>
					<DropdownItem on:click={() => (sort_type = 'type')}>By Storage Type</DropdownItem>
					<DropdownItem on:click={() => (sort_type = 'idnum')}>By Storage ID</DropdownItem>
					<DropdownItem on:click={() => (sort_type = 'detail')}>By Details</DropdownItem>
				</DropdownMenu>
			</Dropdown>
			<Table>
				<thead>
					<th>Name</th>
					{#if includes_email}<th>Email</th>{/if}
					<th>Plan</th>
					<th>Membership</th>
					<th>Start Date</th>
					<th>Type</th>
					<th>ID</th>
					<th>Detail</th>
					<th>Actions</th>
				</thead>
				<tbody>
					{#each subs_sorted as sub, i}
						<tr>
							<td
								>{sub.customer}
								{#if sub.unpaid.length > 0}
									<Badge style="cursor: pointer;" id={'sub' + i} color="danger"
										>{sub.unpaid.length}</Badge
									>
									<Popover target={'sub' + i} placement="right" title="Unpaid invoices">
										{#each sub.unpaid as inv_id}
											<div>
												<a href={'https://app.squareup.com/dashboard/invoices/' + inv_id}
													>{inv_id}</a
												>
											</div>
										{/each}
									</Popover>
								{/if}
							</td>
							{#if includes_email}<td>{sub.email}</td>{/if}
							<td>
								{#if sub.plan == 'Non-Square Agreement'}
									{sub.plan}
								{:else}
									<a href={'https://app.squareup.com/dashboard/subscriptions-list/' + sub.id}
										>{sub.plan}</a
									>
								{/if}
								{#if sub.status !== 'ACTIVE'}
									({sub.status})
								{/if}
							</td>
							<td>{sub.membership_status}</td>
							<td>{sub.start_date}</td>
							<td>
								{#if editing_sub_id === sub.id}
									<Dropdown autoClose={true}>
										<DropdownToggle color="light" caret>{draft_storage_type}</DropdownToggle>
										<DropdownMenu>
											{#each ['Cart', 'Table', 'Parking space', 'Board/bar', 'Sheet', 'Locker', 'Cage', 'Rack', 'Other', 'Unknown'] as typ}
												<DropdownItem on:click={() => set_draft_type(typ)}>{typ}</DropdownItem>
											{/each}
										</DropdownMenu>
									</Dropdown>
								{:else}
									{sub.storage_type}
								{/if}
							</td>
							<td>
								{#if editing_sub_id === sub.id}
									<Input type="text" bind:value={draft_storage_id} aria-label="Storage ID" />
								{:else}
									{sub.storage_id}
								{/if}
							</td>
							<td>
								{#if editing_sub_id === sub.id}
									<Input
										type="text"
										bind:value={draft_storage_detail}
										aria-label="Storage Detail"
									/>
								{:else}
									{sub.storage_detail}
								{/if}
							</td>
							<td>
								{#if editing_sub_id === sub.id}
									<Button
										color="primary"
										size="sm"
										on:click={save_edit}
										disabled={sub_note_editing}
										aria-label={`Save ${sub.customer}`}
									>
										Save
									</Button>
									<Button
										color="secondary"
										size="sm"
										on:click={cancel_edit}
										disabled={sub_note_editing}
										aria-label={`Cancel editing ${sub.customer}`}
									>
										Cancel
									</Button>
								{:else}
									<Button
										color="primary"
										size="sm"
										on:click={() => start_edit(sub)}
										disabled={!sub.editable ||
											sub_note_editing ||
											(editing_sub_id !== null && editing_sub_id !== sub.id)}
										aria-label={`Edit ${sub.customer}`}
									>
										Edit
									</Button>
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</Table>
		</CardBody>
	</Card>
	<div style="height: 120px"></div>
{/if}
