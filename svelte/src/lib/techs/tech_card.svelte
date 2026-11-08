<script type="typescript" lang="ts">
	import {
		Card,
		CardHeader,
		CardTitle,
		CardBody,
		Container,
		Row,
		Col,
		Button,
		Modal,
		Input
	} from '@sveltestrap/sveltestrap';
	import type { DisplayTech } from './types';

	export let tech: DisplayTech;
	export let isCurrentUser: boolean = false;
	export let isTechLead: boolean = false;
	export let onUpdate: (tech: DisplayTech) => void;
	export let onDisenroll: (tech: DisplayTech) => void;
	export let modalOpen: boolean = false;
	export let onToggleModal: () => void;

	let editing = false;
	let draft = {
		shop_tech_shift: '',
		shop_tech_first_day: '',
		shop_tech_last_day: '',
		area_lead: '',
		interest: '',
		expertise: ''
	};

	$: can_edit = isTechLead || isCurrentUser;

	function start_edit() {
		draft = {
			shop_tech_shift: tech.shop_tech_shift,
			shop_tech_first_day: tech.shop_tech_first_day,
			shop_tech_last_day: tech.shop_tech_last_day,
			area_lead: tech.area_lead,
			interest: tech.interest,
			expertise: tech.expertise
		};
		editing = true;
	}

	function cancel_edit() {
		editing = false;
	}

	function save_edit() {
		tech.shop_tech_shift = draft.shop_tech_shift;
		tech.shop_tech_first_day = draft.shop_tech_first_day;
		tech.shop_tech_last_day = draft.shop_tech_last_day;
		tech.area_lead = draft.area_lead;
		tech.interest = draft.interest;
		tech.expertise = draft.expertise;
		editing = false;
		onUpdate(tech);
	}
</script>

<Card class="my-2">
	<CardHeader>
		<div class="d-flex justify-content-between align-items-center">
			<CardTitle>{tech.name} ({tech.email})</CardTitle>
			<div class="d-flex align-items-center gap-1">
				{#if editing}
					<Button color="primary" size="sm" on:click={save_edit} aria-label="Save {tech.name}">
						Save
					</Button>
					<Button
						color="secondary"
						size="sm"
						on:click={cancel_edit}
						aria-label="Cancel editing {tech.name}"
					>
						Cancel
					</Button>
				{:else if can_edit}
					<Button color="primary" size="sm" on:click={start_edit} aria-label="Edit {tech.name}">
						Edit
					</Button>
				{/if}
				{#if isTechLead}
					<Button
						color="danger"
						size="sm"
						on:click={() => onDisenroll(tech)}
						title="Disenroll {tech.name}"
						aria-label="Disenroll {tech.name}"
					>
						Disenroll
					</Button>
				{/if}
			</div>
		</div>
	</CardHeader>
	<CardBody>
		<Container style="max-width: none;">
			<Row cols={{ xl: 2, lg: 2, md: 2, sm: 1, xs: 1 }}>
				<Col>
					<Row cols={{ xl: 2, lg: 2, md: 1, sm: 1, xs: 1 }}>
						{#if tech.volunteer_bio}
							<img
								src={tech.volunteer_picture}
								style="max-width: 200px;"
								alt="Profile picture of {tech.name}"
							/>
							<div>
								<strong>Bio</strong>
								<div>{tech.volunteer_bio}</div>
							</div>
						{:else if isCurrentUser}
							<a href="https://protohaven.org/mugshot" target="_blank">Submit your photo and bio!</a
							>
						{/if}
					</Row>
				</Col>
				<Col>
					<div class="d-flex justify-content-between align-items-center my-1">
						<strong>Shift</strong>
						{#if editing && isTechLead}
							<Input type="text" bind:value={draft.shop_tech_shift} aria-label="Shift" />
						{:else}
							<div class="mx-3">{tech.shop_tech_shift || ''}</div>
						{/if}
					</div>
					<div class="d-flex justify-content-between align-items-center my-1">
						<strong>First Day</strong>
						{#if editing && isTechLead}
							<Input type="text" bind:value={draft.shop_tech_first_day} aria-label="First Day" />
						{:else}
							<div class="mx-3">{tech.shop_tech_first_day || ''}</div>
						{/if}
					</div>
					<div class="d-flex justify-content-between align-items-center my-1">
						<strong>Last Day</strong>
						{#if editing && isTechLead}
							<Input type="text" bind:value={draft.shop_tech_last_day} aria-label="Last Day" />
						{:else}
							<div class="mx-3">{tech.shop_tech_last_day || ''}</div>
						{/if}
					</div>
					<div class="d-flex justify-content-between align-items-center my-1">
						<strong>Area Lead</strong>
						{#if editing && isTechLead}
							<Input type="text" bind:value={draft.area_lead} aria-label="Area Lead" />
						{:else}
							<div class="mx-3">{tech.area_lead || ''}</div>
						{/if}
					</div>
					<div class="d-flex justify-content-between align-items-center my-1">
						<strong>Interest</strong>
						{#if editing && (isTechLead || isCurrentUser)}
							<Input type="text" bind:value={draft.interest} aria-label="Interest" />
						{:else}
							<div class="mx-3">{tech.interest || ''}</div>
						{/if}
					</div>
					<div class="d-flex justify-content-between align-items-center my-1">
						<strong>Expertise</strong>
						{#if editing && (isTechLead || isCurrentUser)}
							<Input type="text" bind:value={draft.expertise} aria-label="Expertise" />
						{:else}
							<div class="mx-3">{tech.expertise || ''}</div>
						{/if}
					</div>
					<Col>
						<Button
							outline
							on:click={onToggleModal}
							aria-label="View {tech.clearances.length} clearance(s) for {tech.name}"
						>
							{tech.clearances.length} Clearance(s)
						</Button>
					</Col>
				</Col>
			</Row>
		</Container>
	</CardBody>
</Card>

<Modal
	body
	header="Clearances"
	isOpen={modalOpen}
	toggle={onToggleModal}
	aria-labelledby="clearances-modal-title"
>
	{#each tech.clearances as c}
		<div>{c}</div>
	{/each}

	{#if isTechLead}
		<div class="my-3">
			<a
				href="https://docs.google.com/forms/d/e/1FAIpQLScX3HbZJ1-Fm_XPufidvleu6iLWvMCASZ4rc8rPYcwu_G33gg/viewform"
				target="_blank"
			>
				Submit additional clearances
			</a>
		</div>
	{/if}
</Modal>
