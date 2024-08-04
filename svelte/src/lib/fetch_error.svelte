<script type="ts">
	export let error;
	import {Alert} from '@sveltestrap/sveltestrap';
</script>

<Alert color="danger">
<div><strong>{error.message}</strong></div>
Try refreshing the page, or <a href="https://api.protohaven.org/logout">Log Out</a> and attempt to load the page again.
</Alert>
