<script type="typescript" lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import {
		Button,
    Icon,
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

	let status: 'initiating' | 'waiting' | 'confirming' | 'success' | 'error' = 'initiating';
	let error_msg: string = '';
  let error_detail: string = '';
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
    console.log("initiate_enrollment()", neon_id, email);
		post('/member/enroll_nfc', { neon_id, email }).then((data) => {
        console.log(data);
        status = 'waiting';
        start_timer();
      }).catch((e) => {
        status = 'error';
        error_msg = 'Failed to start enrollment. Please try again or see staff for help.';
        error_detail = e.toString().substr(0, 128);
        console.error('Enrollment error:', e);
      });
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

  export function on_mqtt_message(data) {
    if (data.origin.endsWith('nfc_written')) {
      console.log('Received NFC write event:', data.data);
      // Only process for the current user
      if (String(data.data.neon_id) === String(neon_id)) {
        // The NFC device reports enrollment complete
        if (status === 'waiting') {
          status = 'confirming';
        }
      }
    }
    // This is a confirmation tap
    else if (data.origin.endsWith('signin')
             && String(data.data.email) === String(email)) {
      if (status === 'waiting' || status === 'confirming') {
        status = 'success';
      }
    }
  }
</script>

<Card>
	<CardBody class="text-center">
		{#if status === 'initiating'}
			<Spinner color="primary" />
			<p class="mt-3">Contacting enrollment system...</p>
		{:else if status === 'waiting'}
			<h2>
        <Icon name="arrow-down-circle" />
        Tap your NFC tag on the reader</h2>
			<p class="text-muted">
        Take a tag and hold it against the <br/>
        NFC reader to enroll it.
			</p>
			<p class="text-muted">
        Wait until you hear a short beep, then a <br/>
        happy chime as the tag enrolls.
			</p>
			<Spinner color="success" size="sm" />
			<p class="text-muted small">Waiting for tag...</p>
		{:else if status === 'confirming'}
			<h2>
        <Icon name="check-circle" />
        Tag enrolled! Try it out:</h2>
			<p class="text-muted">
				Tap again to confirm and test your new tag.
			</p>
			<Spinner color="primary" size="sm" />
			<p class="text-muted small">Waiting for confirmation tap...</p>
		{:else if status === 'success'}
			<h2>
        <Icon name="check-circle-fill" />
        Success!</h2>
			<p>
				Your tag was read successfully and <br/>
        is now linked to your account.<br />
				Next time, just tap to sign in!
			</p>
		{:else if status === 'error'}
			<h2>
        <Icon name="exclamation-triangle" />
        Enrollment Error
      </h2>
			<p class="text-danger">{error_msg}</p>
      <p class="text-muted small"><i>{error_detail}</i></p>
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
