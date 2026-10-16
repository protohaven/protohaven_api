<script type="typescript" lang="ts">
	import {
		Card,
		CardHeader,
		CardTitle,
		CardSubtitle,
		CardBody,
		Spinner
	} from '@sveltestrap/sveltestrap';
	import { get } from '$lib/api.ts';

	interface AreaLeadTech {
		name: string;
		email?: string;
		shift: string[];
	}

	interface AreaLeadsData {
		area_leads: Record<string, AreaLeadTech[]>;
		other_leads: Record<string, AreaLeadTech[]>;
	}

	export let visible: boolean;
	let loaded = false;
	let promise: Promise<AreaLeadsData> = new Promise(() => {});
	function refresh() {
		promise = get('/techs/area_leads').then((data) => {
			loaded = true;
			return data;
		});
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
			<CardTitle>Areas &amp; Leads</CardTitle>
			<CardSubtitle>Contact points for different parts of the shop</CardSubtitle>
		</CardHeader>
		<CardBody>
			{#await promise}
				<Spinner />
			{:then p}
				{#each Object.keys(p['area_leads']) as area}
					<Card color={p['area_leads'][area].length ? undefined : 'warning'}>
						<CardHeader><CardTitle>{area}</CardTitle></CardHeader>
						<CardBody>
							{#each p['area_leads'][area] as tech}
								<div>{tech.name}</div>
								{#if tech.email}<div>{tech.email}</div>{/if}
								{#if tech.shift.length > 0}<div>Shift: {tech.shift.join(' ')}</div>{/if}
							{/each}
						</CardBody>
					</Card>
				{/each}

				<h2 class="my-2">Additional Contacts</h2>
				<em
					>Contacts will appear here if they are assigned an "Area Lead" role for an area which is
					not tracked.</em
				>
				{#if Object.keys(p['other_leads']).length === 0}
					<p class="m-2">No additional contacts found.</p>
				{/if}
				{#each Object.keys(p['other_leads']) as a}
					<Card>
						<CardHeader><CardTitle>{a}</CardTitle></CardHeader>
						<CardBody>
							{#each p['other_leads'][a] as tech}
								<div>{tech.name}</div>
								{#if tech.email}<div>{tech.email}</div>{/if}
								{#if tech.shift.length > 0}<div>Shift: {tech.shift.join(' ')}</div>{/if}
							{/each}
						</CardBody>
					</Card>
				{/each}
			{/await}
		</CardBody>
	</Card>
{/if}
