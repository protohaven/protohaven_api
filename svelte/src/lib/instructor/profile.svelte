<script lang="ts">
	import {
		Image,
		Card,
		CardHeader,
		CardTitle,
		CardSubtitle,
		CardText,
		CardBody,
		Spinner,
		ListGroup,
		ListGroupItem,
		Alert
	} from '@sveltestrap/sveltestrap';
	import FetchError from '../fetch_error.svelte';
	import { is_instructor_onboarded } from './types';

	interface ProfileData {
		fullname?: string;
		profile_img?: string;
		bio?: string;
		email_status?: string;
		active_membership?: string;
		capabilities_listed?: string;
		paperwork?: string;
		discord_user?: string;
		[key: string]: unknown;
	}

	export let profile: Promise<ProfileData | null> | null = null; // Async fetch from parent

	function li_color(v: string | undefined): string {
		const value = (v ?? '').toLowerCase();
		const has_ok = value.indexOf('ok') !== -1;
		return has_ok ? 'light' : 'warning';
	}
</script>

<Card>
	{#await profile}
		<CardHeader>
			<CardTitle>Loading profile...</CardTitle>
		</CardHeader>
		<CardBody><Spinner></Spinner></CardBody>
	{:then p}
		{#if p}
			<CardHeader>
				<CardTitle>
					<div>{p.fullname}</div>
				</CardTitle>
			</CardHeader>
			<CardBody>
				{#if p.profile_img}
					<Image
						fluid
						alt="instructor profile pic"
						src={p.profile_img}
						class="px-5 py-3"
						style="max-height: 20vh; max-width: 20vw"
					/>
				{/if}
				{#if p.bio}
					<CardText>{p.bio}</CardText>
				{/if}
				<CardSubtitle>Status</CardSubtitle>
				<ListGroup>
					<ListGroupItem color={li_color(p.email_status)}>Email: {p.email_status}</ListGroupItem>
					<ListGroupItem color={li_color(p.active_membership)}
						>Membership: {p.active_membership}</ListGroupItem
					>
					<ListGroupItem color={li_color(p.capabilities_listed)}
						>Capabilities: {p.capabilities_listed}</ListGroupItem
					>
					<ListGroupItem color={li_color(p.paperwork)}>Paperwork: {p.paperwork}</ListGroupItem>
					<ListGroupItem color={li_color(p.discord_user)}
						>Discord: {#if p.discord_user == 'missing'}Missing{:else}OK{/if}</ListGroupItem
					>
				</ListGroup>
				{#if !is_instructor_onboarded(p)}
					<Alert color="warning" class="m-3">
						<strong
							>Your status is incomplete. Click <a
								href="https://protohaven.org/wiki/instructors/onboarding"
								target="_blank">HERE</a
							> for required instructor setup steps.</strong
						>
					</Alert>
				{/if}
			</CardBody>
		{:else}
			Loading...
		{/if}
	{:catch error}
		<CardHeader color="danger">
			<CardTitle>Error</CardTitle>
		</CardHeader>
		<CardBody>
			<FetchError {error} />
		</CardBody>
	{/await}
</Card>
