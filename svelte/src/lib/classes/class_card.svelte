<script lang="ts">
	import {
		Button,
		Modal,
		ModalHeader,
		ModalFooter,
		ModalBody,
		Card,
		CardHeader,
		CardTitle,
		Image,
		CardFooter,
		CardBody,
		Icon,
		ListGroup,
		ListGroupItem
	} from '@sveltestrap/sveltestrap';

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

	interface AirtableImage {
		url?: string;
		thumbnails?: {
			large?: {
				url?: string;
			};
		};
	}

	interface ClassCardData {
		price?: string | number;
		hours?: string | number;
		age?: string | number;
		description?: string;
		what_bring_wear?: string;
		what_create?: string;
		instructor?: string;
		dates?: string[];
	}

	export let c: ClassListingItem;

	function open_signup() {
		const url =
			'https://protohaven.app.neoncrm.com/np/clients/protohaven/eventRegistration.jsp?event=' +
			String(c['id']);
		window.open(url, '_blank');
	}

	let img_src = 'https://api.protohaven.org/static/img/favicon.jpg';
	let img_thumb = 'https://api.protohaven.org/static/img/favicon.jpg';
	let data: ClassCardData = {};
	$: {
		const fields = (c['airtable_data'] || { fields: {} }).fields || {};
		const img_data = fields['Image (from Class)'];
		if (Array.isArray(img_data) && img_data.length) {
			const img = img_data[0] as AirtableImage;
			console.log(img_data);
			img_src = img.url ?? img_src;
			if (img.thumbnails?.large?.url) {
				img_thumb = img.thumbnails.large.url;
			} else {
				img_thumb = img_src;
			}
		}

		if (c['airtable_data']) {
			const f = c['airtable_data'].fields || {};

			const dates: string[] = [];
			const startDate = new Date(c['timestamp'] ?? Date.now());
			const days = Number(f['Days (from Class)']) || 0;
			for (let i = 0; i < days; i++) {
				const d = new Date(startDate);
				d.setDate(startDate.getDate() + 7 * i);
				dates.push(d.toLocaleDateString());
			}

			data = {
				price: f['Price (from Class)'] as string | number | undefined,
				hours: f['Hours (from Class)'] as string | number | undefined,
				age: f['Age Requirement (from Class)'] as string | number | undefined,
				description: f['Short Description (from Class)'] as string | undefined,
				what_bring_wear: f['What to Bring/Wear (from Class)'] as string | undefined,
				what_create: f['What you Will Create (from Class)'] as string | undefined,
				instructor: f['Instructor'] as string | undefined,
				dates
			};
		}
	}

	let open = false;
	const toggle = () => (open = !open);
</script>

<Card on:click={toggle} class="my-3" style="cursor:pointer">
	{#if img_thumb}
		<Image fluid src={img_thumb} alt="class image" />
	{/if}
	<CardHeader><CardTitle>{c['name']}></CardTitle></CardHeader>
	<CardBody>
		<ListGroup>
			<ListGroupItem><Icon name="calendar" /> {c['day']}</ListGroupItem>
			<ListGroupItem><Icon name="clock" /> {c['time']}</ListGroupItem>
			{#if data.hours}
				<ListGroupItem><Icon name="hourglass" /> {data.hours}-Hour Workshop</ListGroupItem>
			{/if}
			{#if data.age}
				<ListGroupItem><Icon name="speedometer2" /> Ages {data.age}</ListGroupItem>
			{/if}
		</ListGroup>
	</CardBody>
	{#if data.price}
		<CardFooter>
			${data.price} (members: $TODO)
		</CardFooter>
	{/if}
</Card>

<Modal isOpen={open} {toggle} size="xl">
	<ModalHeader {toggle}>{c['name']}</ModalHeader>
	<ModalBody>
		{#if !c['airtable_data']}
			<!-- eslint-disable-next-line svelte/no-at-html-tags -->
			{@html c['description']}
		{:else}
			<Image fluid src={img_src} alt="class image" />
			<p>{data.description}</p>
			<ListGroup>
				<ListGroupItem>What you will create: {data.what_create}</ListGroupItem>
				<ListGroupItem>What to Bring / Wear: {data.what_bring_wear}</ListGroupItem>
				<ListGroupItem>Age Requirement: {data.age}</ListGroupItem>
				<ListGroupItem>Class Dates: {data.dates}</ListGroupItem>
				<ListGroupItem>Instructor: {data.instructor}</ListGroupItem>
			</ListGroup>
		{/if}
	</ModalBody>
	<ModalFooter>
		<Button color="primary" on:click={() => open_signup()}>Register</Button>
		<Button color="secondary" on:click={toggle}>Close</Button>
	</ModalFooter>
</Modal>
