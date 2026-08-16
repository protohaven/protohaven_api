<script>
	import '../../app.scss';
	import Gcal from '$lib/events/gcal.svelte';
	import Reservations from '$lib/events/reservations.svelte';
	import Classes from '$lib/events/classes.svelte';
</script>

<svelte:head>
	<title>Events Dashboard</title>
</svelte:head>

<Gcal />
<Reservations />
<Classes />
