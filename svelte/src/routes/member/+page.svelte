<script type="typescript" lang="ts">
	import '../../app.scss';
	import { onMount } from 'svelte';
	import { get, post } from '$lib/api.ts';

	import FetchError from '$lib/fetch_error.svelte';
	import Clearances from '$lib/member/clearances.svelte';
	import Recertification from '$lib/member/recertification.svelte';
	import {
		Icon,
		Card,
		Spinner,
		CardTitle,
		CardHeader,
		CardBody,
		CardFooter,
		Button,
		Input,
		Navbar,
		NavbarBrand,
		Nav,
		NavItem,
		NavLink
	} from '@sveltestrap/sveltestrap';

	type Whoami = {
		fullname: string;
		email: string;
		neon_id: string;
		roles: string[];
		clearances: string[];
	};

	type RecertData = {
		pending: unknown[];
		configs: unknown[];
	};

	let discord_id = '';
	let show_discord_setup = false;
	let neon_id: string | null = null;

	const tab_titles = {
		clearances: 'Clearances',
		recertification: 'Recertification'
	};

	let activeTab: string = 'clearances';
	$: page_title = `Member Dashboard: ${(tab_titles as Record<string, string>)[activeTab] || 'Clearances'}`;

	let promise: Promise<Whoami> = new Promise<Whoami>(() => {});
	let recertPromise: Promise<RecertData | null> = new Promise<RecertData | null>(() => {});
	onMount(() => {
		activeTab = (window.location.hash || '#clearances').substring(1).trim();
		const urlParams = new URLSearchParams(window.location.search);
		discord_id = urlParams.get('discord_id') || '';
		show_discord_setup = discord_id !== '';
		neon_id = urlParams.get('neon_id') || null;
		promise = get('/whoami').then((data: Whoami) => {
			neon_id = neon_id || data.neon_id;
			return data;
		});
		recertPromise = get('/member/recert_data').catch((e) => {
			if (e.toString().indexOf('Not yet enabled') !== -1) {
				console.log('Recert dashboard not yet enabled; continuing without');
				return null;
			}
			throw e;
		});
	});

	$: {
		if (!discord_id) {
			feedback = 'Please type your discord user name.';
		} else {
			feedback = null;
		}
	}

	let feedback: string | null = null;
	let output: string | null = null;
	let submitting = false;
	let submit_promise: Promise<void> = Promise.resolve();
	function set_discord() {
		output = null;
		submitting = true;
		submit_promise = post('/member/set_discord', { discord_id, neon_id })
			.then(() => {
				output = 'Discord user set successfully.';
			})
			.finally(() => {
				submitting = false;
			});
	}

	function match(array1: string[], array2: string[]) {
		const filteredArray = array1.filter((value) => array2.includes(value));
		return filteredArray.length > 0;
	}

	function on_tab(e: MouseEvent) {
		activeTab = (e.target as HTMLAnchorElement).href.split('#')[1] || 'clearances';
		window.location.hash = activeTab;
		console.log('activeTab', activeTab);
	}
</script>

<svelte:head>
	<title>{page_title}</title>
</svelte:head>

{#await promise}
	<Spinner />Loading...
{:then p}
	<Navbar color="secondary-subtle">
		<NavbarBrand>Member Dashboard</NavbarBrand>
		<Nav>
			<NavItem>
				<div class="d-flex flex-row">
					{p.fullname} ({p.email}, {p.neon_id})
					<NavLink href="/logout">Logout</NavLink>
				</div>
			</NavItem>
		</Nav>
	</Navbar>

	{#if show_discord_setup}
		<Card class="my-3">
			<CardHeader>
				<CardTitle>Discord Account</CardTitle>
			</CardHeader>
			<CardBody>
				<p>
					Associate a new discord user: <Input
						type="text"
						bind:value={discord_id}
						invalid={feedback !== null}
						feedback={feedback ?? undefined}
					></Input>
				</p>
			</CardBody>
			<CardFooter>
				<Button on:click={set_discord} disabled={submitting || feedback !== null}>Save</Button>
				{#await submit_promise}
					<Spinner />
				{:then}
					{#if output}{output}{/if}
				{:catch error}
					<FetchError {error} nohelp />
				{/await}
			</CardFooter>
		</Card>
	{/if}

	<Nav tabs>
		<NavItem><NavLink href="#clearances" on:click={on_tab}>Clearances</NavLink></NavItem>
		{#await recertPromise then rc}
			{#if rc}
				<NavItem
					><NavLink href="#recertification" on:click={on_tab}>
						{#await recertPromise then rc2}
							{#if rc2 && rc2.pending && rc2.pending.length > 0}
								<Icon name="exclamation-triangle" />
							{/if}
						{/await}
						Recertification
					</NavLink></NavItem
				>
			{/if}
		{/await}
		<NavItem>
			<a class="ph-link" href="/events" target="_blank">Shop Status</a>
		</NavItem>
		{#if match(['Instructor', 'Private Instructor', 'Education Lead', 'Board Member', 'Staff'], p.roles)}
			<NavItem>
				<a class="ph-link" href="/instructor" target="_blank">Instructor Dashboard</a>
			</NavItem>
		{/if}
		{#if match(['Shop Tech', 'Shop Tech Lead', 'Education Lead', 'Board Member', 'Staff'], p.roles)}
			<NavItem>
				<a class="ph-link" href="/techs" target="_blank">Shop Tech Dashboard</a>
			</NavItem>
		{/if}
		{#if match(['Board Member', 'Staff'], p.roles)}
			<NavItem>
				<a class="ph-link" href="/staff" target="_blank">Staff Tools</a>
			</NavItem>
		{/if}
	</Nav>
	<Clearances clearances={p.clearances || []} visible={activeTab == 'clearances'} />
	{#await recertPromise}
		<Spinner />Loading...
	{:then rc}
		{#if rc}
			<Recertification {rc} visible={activeTab == 'recertification'} />
		{/if}
	{:catch error}
		<Card class="my-3">
			<FetchError {error} />
		</Card>
	{/await}
{:catch error}
	<FetchError {error} />
{/await}

<style type="css">
	.ph-link {
		display: block;
		padding: var(--bs-nav-link-padding-y) var(--bs-nav-link-padding-x);
		font-size: var(--bs-nav-link-font-size);
		font-weight: var(--bs-nav-link-font-weight);
		color: var(--bs-nav-link-color);
		text-decoration: none;
		background: none;
		border: 0;
	}
</style>
