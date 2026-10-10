<script type="typescript" lang="ts">
	import '../../app.scss';
	import { onMount } from 'svelte';
	import { get } from '$lib/api.ts';

	import {
		Icon,
		Container,
		Navbar,
		NavbarBrand,
		Button,
		Nav,
		NavItem,
		NavLink,
		Spinner
	} from '@sveltestrap/sveltestrap';
	import ClassDetails from '$lib/instructor/class_details.svelte';
	import Profile from '$lib/instructor/profile.svelte';
	import Scheduler from '$lib/instructor/scheduler.svelte';
	import InstructorList from '$lib/instructor/instructor_list.svelte';
	import ClassTemplates from '$lib/instructor/class_templates.svelte';
	import FetchError from '$lib/fetch_error.svelte';
	import { is_instructor_onboarded } from '$lib/instructor/types';
	import type { InstructorListData } from '$lib/instructor/types';

	interface WhoAmI {
		fullname?: string;
		email?: string;
		roles?: string[];
		[key: string]: unknown;
	}

	interface SchedulerClassTemplate {
		class_id: string;
		name: string;
		hours: number[];
		capacity: number;
		price: number;
		period: number;
		areas: string[];
		clearances: string[];
	}

	interface InstructorProfile {
		email?: string;
		fullname?: string;
		airtable_id?: string;
		classes?: Record<string, string>;
		active_membership?: string;
		capabilities_listed?: string;
		paperwork?: string;
		discord_user?: string;
		[key: string]: unknown;
	}

	let promise: Promise<unknown> = Promise.resolve(null);
	let admin = false;
	let user: WhoAmI | null = null;

	const tab_titles: Record<string, string> = {
		classes: 'Classes',
		profile: 'Profile',
		roster: 'Roster',
		templates: 'Class Templates'
	};

	let activeTab = 'classes';
	$: page_title = `Instructor Dashboard: ${tab_titles[activeTab] || 'Classes'}`;
	onMount(() => {
		activeTab = (window.location.hash || '#classes').substring(1).trim();
		const urlParams = new URLSearchParams(window.location.search);
		const e = urlParams.get('email');
		console.log(`E is ${e}; fetching /whoami`);
		try {
			// Initial /whoami takes time to fetch and delays page interaction,
			// so we serve a cached version before the request completes.
			const cachedRaw = localStorage.getItem('whoami_cache');
			if (cachedRaw) {
				const cached = JSON.parse(cachedRaw);
				user = cached.user;
				admin = cached.admin;
			}
		} catch (e) {
			console.warn('Cache lookup failed: ', e);
		}
		promise = get('/whoami').then((d) => {
			console.log(d);
			admin = (d.roles || []).some((role: string) =>
				['Tech Lead', 'Education Lead', 'Admin', 'Board Member', 'Staff'].includes(role)
			);
			user = d;
			try {
				localStorage.setItem('whoami_cache', JSON.stringify({ admin, user }));
			} catch (e) {
				console.warn('Cache store failed: ', e);
			}
			if (!e) {
				promise = Promise.resolve(d);
				fetch_instructor_profile(d.email);
			} else {
				promise = Promise.resolve({ email: e });
				fetch_instructor_profile(e);
			}
			if (admin) {
				fetch_instructor_list();
			}
			return d;
		});
	});

	function on_tab(e: MouseEvent) {
		const target = e.target as HTMLAnchorElement;
		if (!target.href) {
			return;
		}
		activeTab = target.href.split('#')[1] || 'classes';
		window.location.hash = activeTab;
		console.log('activeTab', activeTab);
	}

	let profile: Promise<InstructorProfile> = new Promise<InstructorProfile>(() => {});
	let templates: Promise<Record<string, SchedulerClassTemplate>> = Promise.resolve({});
	let instructorListData: Promise<InstructorListData> | null = null; // Store instructor list data for admin tabs
	function fetch_instructor_list() {
		instructorListData = get('/instructor/list');
	}

	function fetch_instructor_profile(email: string) {
		const url = '/instructor/about?email=' + encodeURIComponent(email);
		console.log(`getting profile data for email ${email} -> ${url}`);
		profile = get(url)
			.then((result) => {
				console.log('Instructor profile:', result);
				if (result.classes) {
					console.log('Seeking templates for classes:', result.classes);
					templates = get(
						'/instructor/class/templates?ids=' +
							encodeURIComponent(Object.keys(result.classes).join(','))
					);
				}

				return result;
			})
			.catch((e) => {
				console.log(e);
				throw e;
			});
	}

	let scheduler_open = false;
</script>

<svelte:head>
	<title>{page_title}</title>
</svelte:head>

<Navbar color="primary-subtle" sticky="">
	<NavbarBrand>Instructor Dashboard</NavbarBrand>
	<Nav>
		<NavItem>
			<NavLink
				href="https://docs.google.com/forms/d/e/1FAIpQLScX3HbZJ1-Fm_XPufidvleu6iLWvMCASZ4rc8rPYcwu_G33gg/viewform"
				target="_blank">Log Form (Blank)</NavLink
			>
		</NavItem>
		<NavItem>
			<NavLink href="https://wiki.protohaven.org/books/instructors-handbook" target="_blank"
				>Wiki/Help</NavLink
			>
		</NavItem>
		<NavItem>
			{#await promise}
				<Spinner />
			{:then}
				{#if !user || !user.fullname}
					<NavLink href="http://api.protohaven.org/login?referrer=/techs">Login</NavLink>
				{:else}
					<NavLink href="/logout">{user.fullname} (Logout)</NavLink>
				{/if}
			{/await}
		</NavItem>
	</Nav>
</Navbar>
<!-- Note: Nav is used here instead of Tabs directly because Tabs does not
     support URL anchor based routing - see
     https://github.com/sveltestrap/sveltestrap/issues/82 -->
<Nav tabs>
	<NavItem><NavLink href="#classes" on:click={on_tab}>Classes</NavLink></NavItem>
	<NavItem
		><NavLink href="#profile" on:click={on_tab}>
			Profile
			{#await profile}
				...
			{:then p}
				<Icon name={is_instructor_onboarded(p) ? 'check-all' : 'exclamation-triangle'} />
			{/await}
		</NavLink></NavItem
	>
	{#if admin}
		<NavItem><NavLink href="#roster" on:click={on_tab}>Roster</NavLink></NavItem>
		<NavItem><NavLink href="#templates" on:click={on_tab}>Class Templates</NavLink></NavItem>
	{/if}
</Nav>
{#await promise}
	<Spinner />
	<strong>Resolving instructor data...</strong>
{:then}
	<main>
		<Container>
			{#await profile}
				<Spinner />
			{:then p}
				<Scheduler
					email={p.email ?? ''}
					classes={p.classes || {}}
					{templates}
					bind:open={scheduler_open}
				/>

				<!-- Profile Tab -->
				{#if activeTab === 'profile'}
					<Profile {profile} />
				{/if}

				<!-- Classes Tab -->
				{#if activeTab === 'classes'}
					<Button
						class="mx-2"
						disabled={p.capabilities_listed === 'missing'}
						on:click={() => {
							scheduler_open = true;
						}}>Open Scheduler</Button
					>

					<ClassDetails email={p.email} {scheduler_open} />
				{/if}

				<!-- Roster Tab (Admin only) -->
				{#if admin && activeTab === 'roster'}
					{#await instructorListData}
						<Spinner />
						<strong>Loading instructor roster...</strong>
					{:then data}
						<InstructorList
							{data}
							{admin}
							visible={activeTab === 'roster'}
							onEnrollmentChanged={fetch_instructor_list}
						/>
					{:catch error}
						<FetchError {error} />
					{/await}
				{/if}

				<!-- Class Templates Tab (Admin only) -->
				{#if admin && activeTab === 'templates'}
					{#await instructorListData}
						<Spinner />
						<strong>Loading class templates...</strong>
					{:then data}
						<ClassTemplates {data} visible={activeTab === 'templates'} />
					{:catch error}
						<FetchError {error} />
					{/await}
				{/if}
			{:catch error}
				<FetchError {error} />
			{/await}
		</Container>
	</main>
{:catch error}
	<FetchError {error} />
{/await}

<style>
	main {
		width: 100%;
		padding: 15px;
		margin: 0 auto;
		display: flex;
		flex-direction: row;
		justify-content: center;
		align-items: flex-start;
	}
</style>
