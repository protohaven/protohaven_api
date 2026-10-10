<script lang="ts">
	import '../../app.scss';
	import { get } from '$lib/api.ts';
	import { Row, Col, Container, Spinner } from '@sveltestrap/sveltestrap';
	import { onMount } from 'svelte';
	import ClassCard from '$lib/classes/class_card.svelte';

	interface ClassListingItem {
		id?: string | number;
		name?: string;
		day?: string;
		time?: string;
		timestamp?: string | number;
		description?: string;
		airtable_data?: {
			fields?: Record<string, unknown>;
		};
	}

	let promise: Promise<ClassListingItem[]> = Promise.resolve([]);
	onMount(() => {
		promise = get('/class_listing').then((data: ClassListingItem[]) => {
			console.log(data);
			const acc: ClassListingItem[] = [];
			for (const c of data) {
				const name = String(c['name'] ?? '');
				if (
					name.indexOf('New Member Orientation') !== -1 ||
					name.indexOf('Private Instruction') !== -1
				) {
					continue;
				}
				acc.push(c);
			}
			return acc;
		});
	});
</script>

<svelte:head>
	<title>Classes</title>
</svelte:head>

<main>
	{#await promise}
		<Spinner />
	{:then result}
		{#if result}
			<Container>
				<Row cols={{ lg: 3, md: 2, sm: 1 }}>
					{#each result as c}
						<Col>
							<ClassCard {c} />
						</Col>
					{/each}
				</Row>
			</Container>
		{:else}
			<Spinner />
		{/if}
	{:catch error}
		TODO error {error.message}
	{/await}
</main>

<style>
	main {
		width: 100%;
		padding: 15px;
		margin: 0 auto;

		display: -ms-flexbox;
		display: -webkit-box;
		display: flex;
		flex-direction: column;
		-ms-flex-align: center;
		-ms-flex-pack: center;
		-webkit-box-align: center;
		align-items: center;
		-webkit-box-pack: center;
		justify-content: center;
		padding-top: 40px;
		padding-bottom: 40px;
		background-color: #f8f8f8;
	}
</style>
