<script type="typescript" lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import {
		Button,
		Row,
		Col,
		Card,
		CardBody,
		CardFooter,
		Spinner
	} from '@sveltestrap/sveltestrap';
	import { post } from '$lib/api.ts';

	export let neon_id: string;
	export let email: string;
	export let on_close: () => void;
	export let on_enrolled: () => void;

	let status: 'initiating' | 'waiting' | 'confirming' | 'success' | 'error' = 'initiating';
	let error_msg: string = '';
	let count: number = 60;
	let interval: ReturnType<typeof setInterval> | null = null;

	onMount(() => {
		initiate_enrollment();
	});

	onDestroy(() => {
		if (interval) clearInterval(interval);
	});

	async function initiate_enrollment() {
		status = 'initiating';
		try {
			await post('/user/enroll_nfc', { neon_id, email });
			status = 'waiting';
			start_timer();
		} catch (e) {
			status = 'error';
			error_msg = 'Failed to start enrollment. Please try again or see staff for help.';
			console.error('Enrollment error:', e);
		}
	}

	function start_timer() {
		count = 60;
		interval = setInterval(() => {
			count -= 1;
			if (count <= 0) {
				clearInterval(interval!);
				interval = null;
				on_close();
			}
		}, 1000);
	}

	export function on_tap_detected() {
		// Called by parent when an NFC sign-in tap is detected during enrollment
		// This confirms the enrollment was successful
		if (status === 'waiting' || status === 'confirming') {
			status = 'success';
			if (interval) {
				clearInterval(interval);
				interval = null;
			}
			// Give user a moment to see the success, then signal completion
			setTimeout(() => on_enrolled(), 2000);
		}
	}

	export function on_last_enrollment(data: { timestamp: string; nfc_id: string }) {
		// Called by parent when the NFC device reports enrollment complete
		if (status === 'waiting') {
			status = 'confirming';
		}
	}
</script>

<Card>
	<Row class="text-center my-4">
		<Col>
			<h2>NFC Tag Enrollment</h2>
		</Col>
	</Row>

	<CardBody class="text-center">
		{#if status === 'initiating'}
			<Spinner color="primary" />
			<p class="mt-3">Contacting enrollment system...</p>
		{:else if status === 'waiting'}
			<div style="font-size: 3em; margin-bottom: 0.5em;">📱</div>
			<h4>Tap your NFC tag on the reader</h4>
			<p class="text-muted">
				Hold your tag, badge, or phone against the NFC reader<br />
				on the kiosk to enroll it.
			</p>
			<Spinner color="success" size="sm" />
			<p class="text-muted small">Waiting for tag...</p>
		{:else if status === 'confirming'}
			<div style="font-size: 3em; margin-bottom: 0.5em;">✅</div>
			<h4>Tag enrolled!</h4>
			<p class="text-muted">
				Tap again to confirm and test your new tag.
			</p>
			<Spinner color="primary" size="sm" />
			<p class="text-muted small">Waiting for confirmation tap...</p>
		{:else if status === 'success'}
			<div style="font-size: 3em; margin-bottom: 0.5em;">🎉</div>
			<h4>Enrollment Complete!</h4>
			<p>
				Your NFC tag is now linked to your account.<br />
				Next time, just tap to sign in!
			</p>
		{:else if status === 'error'}
			<div style="font-size: 3em; margin-bottom: 0.5em;">⚠️</div>
			<h4>Enrollment Error</h4>
			<p class="text-danger">{error_msg}</p>
		{/if}
	</CardBody>

	<CardFooter class="text-center">
		<Row class="justify-content-center">
			<Col sm={{ size: 'auto' }}>
				<Button color="secondary" on:click={on_close}>
					{#if status === 'error'}
						Go Back
					{:else}
						Cancel (closes in {count}s)
					{/if}
				</Button>
			</Col>
		</Row>
	</CardFooter>
</Card>

<style>
	p {
		margin-bottom: 0.5rem;
	}
</style>
