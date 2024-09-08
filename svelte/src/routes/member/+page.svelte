<script type="ts">
  import '../../app.scss';
  import { onMount } from 'svelte';
  import {get, post} from '$lib/api.ts';

  import FetchError from '$lib/fetch_error.svelte';
  import { Card, Spinner, CardTitle, CardHeader, CardBody, CardFooter, Button, Input } from '@sveltestrap/sveltestrap';

  let first;
  let last;
  let discord_id;
  let neon_id;

  let promise = new Promise(()=>{});
  onMount(() => {
	  const urlParams = new URLSearchParams(window.location.search);
	  discord_id = urlParams.get("discord_id") || "";
	  neon_id = urlParams.get("neon_id") || null;
	  promise = get("/whoami");
  });

  $: {
    if (!discord_id) {
	feedback = "Please type your discord user name.";
    } else {
    	feedback = null;
    }
  }

  let feedback;
  let output;
  let submitting = false;
  let submit_promise = new Promise((res,rej) => res(null));
  function set_discord() {
    output = null;
    submitting = true;
    submit_promise = post("/member/set_discord", {discord_id, neon_id}).then((data) => {
	output = "Discord user set successfully.";
    }).finally(()=> {submitting = false;});
  }

</script>

<main>
	{#await promise}
	<Spinner/>
	{:then p}
	<Card>
	<CardHeader>
	<CardTitle>Discord Account Association</CardTitle>
	</CardHeader>
	<CardBody>
		<p>Hello, {p.fullname}!</p>
		<p>Associate a new discord user: <Input type="text" bind:value={discord_id} invalid={feedback} feedback={feedback}></Input></p>
	</CardBody>
	<CardFooter>
		<Button on:click={set_discord} disabled={submitting || feedback}>Save</Button>
		{#await submit_promise}
		<Spinner/>
		{:then d}
			{#if output}{output}{/if}
		{:catch error}
			<FetchError {error} nohelp/>
		{/await}
	</CardFooter>
	</Card>
	{:catch error}
	  <FetchError {error}/>
	{/await}
</main>


<style>
		img {
			max-width: 600px;
			margin-left: auto;
			margin-right: auto;
		}
		main {
			width: 100%;
			padding: 15px;
			margin: 0 auto;

			display: -ms-flexbox;
			display: -webkit-box;
			display: flex;
			flex-direction: column;
			-ms-flex-align: center;
			-ms-flex-pack: center;
			-webkit-box-align: center;
			align-items: center;
			-webkit-box-pack: center;
			justify-content: center;
			padding-top: 40px;
			padding-bottom: 40px;
  			background-color: #f8f8f8;
		}
</style>
