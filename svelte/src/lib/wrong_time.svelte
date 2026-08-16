<script type="typescript">
	import { Alert, Button, Row, Col } from '@sveltestrap/sveltestrap';
	export let on_continue;
	export let on_close;
	export let name;
	export let membership_window = '';
</script>

<Alert color="warning" fade={false} isOpen={true}>
	<Row class="text-center justify-content-center">
		<h1>Heads up, {name}.</h1>
		<h3>Your membership doesn't cover the current day/time.</h3>
		{#if membership_window}
			<p>Your membership is valid: <strong>{membership_window}</strong>.</p>
		{/if}
		<p>
			If you are attending an evening class or event, or have staff approval to use the shop, you
			can continue signing in.
		</p>
	</Row>

	<Row class="justify-content-center">
		<Col sm={{ size: 'auto' }} class="my-3">
			<Button color="primary" on:click={on_continue}>
				I'm attending an evening class or event
			</Button>
		</Col>
		<Col sm={{ size: 'auto' }} class="my-3">
			<Button color="warning" on:click={on_continue}>Sign in anyway</Button>
		</Col>
		<Col sm={{ size: 'auto' }} class="my-3">
			<Button color="secondary" on:click={on_close}>Go back</Button>
		</Col>
	</Row>
</Alert>
