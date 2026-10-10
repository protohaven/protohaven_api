<script type="typescript" lang="ts">
	import {
		Alert,
		Modal,
		ModalBody,
		ModalFooter,
		Button,
		ListGroup,
		ListGroupItem,
		Input,
		Spinner
	} from '@sveltestrap/sveltestrap';
	import { get, post, del } from '$lib/api.ts';
	import FetchError from '../fetch_error.svelte';
	import { onMount } from 'svelte';

	interface ForecastOverride {
		id?: string;
		date?: string;
		ap?: string;
		techs: string[];
		orig?: string[];
		editor?: string;
		fullname?: string;
		email?: string;
		[key: string]: unknown;
	}

	interface TechOption {
		name: string;
		shift: string;
	}

	export let edit: ForecastOverride | null = null; // obj with `date`, `ap`, `techs`, `orig`, `email`, `fullname`
	let all_techs: Promise<TechOption[]> = new Promise(() => {});
	onMount(() => {
		all_techs = get('/techs/list').then((data) => {
			let tt = data.techs.map((t: TechOption) => {
				return { name: t.name, shift: t.shift };
			});
			tt.sort((a: TechOption, b: TechOption) => a.name.localeCompare(b.name));
			return tt;
		});
	});
	export let on_update: () => void;

	const EDIT_ROLES = ['Tech Lead', 'Education Lead', 'Admin', 'Board Member', 'Staff'];
	$: can_edit =
		edit !== null &&
		Array.isArray(edit.roles) &&
		edit.roles.some((role: string) => EDIT_ROLES.includes(role));

	function rm(tech: string) {
		if (!edit) {
			return;
		}
		edit.techs = edit.techs.filter((t: string) => t != tech);
	}

	let selected = '';
	let custom_text = '';
	function add_custom() {
		if (!edit) {
			return;
		}
		edit.techs.push(custom_text);
		edit = edit; // Trigger update
		custom_text = '';
		selected = '';
	}
	function selection_changed() {
		if (selected === 'custom' || selected === '') {
			return;
		}
		if (!edit) {
			return;
		}
		edit.techs.push(selected);
		edit = edit; // Trigger update
		selected = '';
	}

	let promise: Promise<unknown> = new Promise((resolve) => {
		resolve(null);
	});
	let acting = false;
	function save() {
		acting = true;
		promise = post('/techs/forecast/override', edit)
			.then(() => {
				edit = null;
				on_update();
			})
			.finally(() => (acting = false));
	}
	function revert() {
		acting = true;
		promise = del('/techs/forecast/override', edit)
			.then(() => {
				edit = null;
				on_update();
			})
			.finally(() => (acting = false));
	}
</script>

<Modal isOpen={edit !== null} header="{edit && edit.date} {edit && edit.ap}">
	<ModalBody>
		{#if edit}
			Current shift:
			<ListGroup>
				{#if edit.techs.length == 0}
					No techs on shift
				{/if}
				{#each edit.techs as t}
					<ListGroupItem>
						{#if can_edit}
							<Button on:click={() => rm(t)}>X</Button>&nbsp;
						{/if}{t}</ListGroupItem
					>
				{/each}
				{#if can_edit}
					<ListGroupItem>
						{#await all_techs}
							<Spinner />
						{:then tt}
							<Input type="select" bind:value={selected} on:change={selection_changed}>
								<option value="">Add new...</option>
								{#each tt as t}
									<option value={t.name}
										>{t.name}{#if t.shift}&nbsp;(from {t.shift}){/if}</option
									>
								{/each}
								<option value="custom">Custom...</option>
							</Input>
							{#if selected == 'custom'}
								<div class="d-flex flex-row">
									<Input type="text" bind:value={custom_text} placeholder="Custom Tech" />
									<Button on:click={add_custom}>Add</Button>
								</div>
							{/if}
						{:catch error}
							<FetchError {error} />
						{/await}
					</ListGroupItem>
				{/if}
			</ListGroup>
		{/if}
	</ModalBody>
	<ModalFooter>
		<div style="width: 100%">
			{#if !can_edit}
				<Alert color="warning"
					>You must be <a href="https://api.protohaven.org/login">logged in</a> to modify the shift schedule</Alert
				>
			{/if}
			{#if edit?.id}
				Original:
				{#each edit?.orig ?? [] as t}
					<ul>
						<li>{t}</li>
					</ul>
				{/each}
				<em>Last edit: {edit.editor}</em>
			{/if}
		</div>
		{#await promise}
			<Spinner />
		{:catch error}
			<FetchError {error} />
		{/await}
		<Button color="primary" on:click={save} disabled={acting || !can_edit}>Save</Button>
		{#if edit?.id}
			<Button color="primary" on:click={revert} disabled={acting || !can_edit}>Revert</Button>
		{/if}
		<Button color="secondary" on:click={() => (edit = null)} disabled={acting}>Cancel</Button>
	</ModalFooter>
</Modal>
