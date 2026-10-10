<script lang="ts">
	import { Alert } from '@sveltestrap/sveltestrap';

	type ErrorLike = { message: string };

	export let error: ErrorLike;
	export let nohelp = false;
</script>

<Alert color="danger">
	<div><strong>{error.message}</strong></div>
	{#if !nohelp}
		Try refreshing the page, or <a href="https://api.protohaven.org/logout">Log Out</a> and attempt to
		load the page again.
	{/if}
</Alert>
