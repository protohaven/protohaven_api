<script lang="ts">
	import '../../app.scss';
	import { Spinner, Navbar, NavItem, NavbarBrand, NavLink, Nav } from '@sveltestrap/sveltestrap';
	import SummarizeDiscord from '$lib/staff/summarize_discord.svelte';
	import { onMount } from 'svelte';
	import { get } from '$lib/api.ts';
	import OpsReport from '$lib/staff/ops_report.svelte';

	interface WhoAmI {
		fullname?: string;
		email?: string;
		[key: string]: unknown;
	}

	const tab_titles: Record<string, string> = {
		summary: 'Discord Summary',
		opsreport: 'Ops Report'
	};

	let activeTab = 'summary';
	$: page_title = `Staff Dashboard: ${tab_titles[activeTab] || 'Discord Summary'}`;
	let user: WhoAmI | null = null;
	let promise: Promise<unknown> = Promise.resolve(null);
	onMount(() => {
		activeTab = (window.location.hash || '#summary').substring(1).trim();
		console.log('active', activeTab);
		promise = get('/whoami')
			.then((d) => {
				user = d;
				return d;
			})
			.catch((e) => {
				if (e.message.indexOf('You are not logged in') !== -1) {
					return '';
				}
				throw e;
			});
	});
	function on_tab(e: MouseEvent) {
		const target = e.target as HTMLAnchorElement;
		activeTab = target.href.split('#')[1] || 'summary';
		window.location.hash = activeTab;
		console.log('activeTab', activeTab);
	}
</script>

<svelte:head>
	<title>{page_title}</title>
</svelte:head>

<Navbar color="primary-subtle" sticky="">
	<NavbarBrand>Staff Dashboard</NavbarBrand>
	<Nav>
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

<Nav tabs>
	<NavItem><NavLink href="#summary" on:click={on_tab}>Discord Summary</NavLink></NavItem>
	<NavItem><NavLink href="#opsreport" on:click={on_tab}>Ops Report</NavLink></NavItem>
</Nav>
<SummarizeDiscord visible={activeTab == 'summary'} {user} />
<OpsReport visible={activeTab == 'opsreport'} />
