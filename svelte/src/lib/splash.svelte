<script type="typescript" lang="ts">
	import { Button, Row, Col, Card, Input, Progress, FormGroup } from '@sveltestrap/sveltestrap';
	import { onMount, onDestroy } from 'svelte';

	type ProgressState = {
		pct: number;
		msg: string;
	} | null;

	export let on_member: () => void;
	export let on_guest: () => void;
	export let feedback: string | null;
	export let email: string | null;
	export let progress: ProgressState;
	export let dependent_info: string;
	let has_dependents = false;

	async function reset() {
		email = '';
		progress = null;
		dependent_info = '';
		has_dependents = false;
	}
	reset();

	$: submit_enabled =
		email && email.trim() != '' && !progress && !(has_dependents && dependent_info == '');

	// Shortcut for members; only if valid form state
	function check_enter_key_submit(e: KeyboardEvent) {
		if (e.key == 'Enter' && submit_enabled) {
			on_member();
		}
	}

	// Inactivity timer - reset for the next person
	let count: number | null = null;
	let interval: ReturnType<typeof setInterval> | undefined;
	function updateTimer() {
		count = (count ?? 0) - 1;
		// console.log(count);
	}
	function extendTimer() {
		if (interval === undefined) {
			interval = setInterval(updateTimer, 1000);
		}
		count = 60;
	}

	onMount(() => {
		addEventListener('keypress', extendTimer);
		addEventListener('mousemove', extendTimer);
	});
	onDestroy(() => {
		if (interval !== undefined) clearInterval(interval);
	});

	$: if (count === 0) {
		if (interval !== undefined) {
			clearInterval(interval);
			interval = undefined;
		}
		reset();
	}
</script>

<Card>
	<Row>
		<Col class="text-center my-5">
			<h1>Welcome! Please sign in:</h1>
			<em>If you are a member, you must use the email that's linked to your membership.</em>
		</Col>
	</Row>

	<Row class="mx-5">
		<Col>
			<FormGroup>
				<Input
					type="email"
					autofocus
					disabled={progress !== null}
					placeholder="Your email address here"
					bind:value={email}
					invalid={feedback !== null}
					feedback={feedback ?? undefined}
					on:keydown={check_enter_key_submit}
				/>
			</FormGroup>
		</Col>
		{#if progress}
			<Progress color="info" value={progress.pct}>{progress.msg}</Progress>
		{/if}
	</Row>

	<Row class="justify-content-center">
		<Col sm={{ size: 'auto' }}>
			<Input
				bind:checked={has_dependents}
				type="checkbox"
				label="I am signing in one or more children under age 18"
				tabindex={-1}
			/>
			{#if has_dependents}
				<Input
					type="email"
					disabled={progress !== null}
					placeholder="Enter child name(s) here"
					bind:value={dependent_info}
				/>
			{/if}
		</Col>
	</Row>

	<Row class="justify-content-center text-center mt-5">
		<h3>I am a...</h3>
	</Row>

	<Row class="d-flex justify-content-center my-3">
		<Col sm={{ size: 'auto' }} class="mr-3">
			<Button size="lg" disabled={!submit_enabled} color="primary" on:click={on_member}
				>Member</Button
			>
		</Col>
		<Col sm={{ size: 'auto' }}>
			<Button size="lg" disabled={!submit_enabled} color="light" on:click={on_guest}>Guest</Button>
		</Col>
	</Row>
</Card>
