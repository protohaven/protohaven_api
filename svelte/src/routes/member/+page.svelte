<script type="typescript">
  import '../../app.scss';
  import { onMount } from 'svelte';
  import {get, post} from '$lib/api.ts';

  import FetchError from '$lib/fetch_error.svelte';
  import { Badge, Card, Spinner, ListGroup, ListGroupItem, CardTitle, CardSubtitle, CardHeader, CardBody, CardFooter, Button, Input, Navbar, NavbarBrand, Nav, NavItem, NavLink } from '@sveltestrap/sveltestrap';

  let first;
  let last;
  let discord_id;
  let show_discord_setup = false;
  let neon_id;

  let promise = new Promise(() => {});
  onMount(() => {
	  const urlParams = new URLSearchParams(window.location.search);
	  discord_id = urlParams.get("discord_id") || "";
    show_discord_setup = discord_id !== "";
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

  function match(array1, array2) {
    const filteredArray = array1.filter(value => array2.includes(value));
    return filteredArray.length > 0;
  }
</script>

{#await promise}
<Spinner/>Loading...
{:then p}
<Navbar color="secondary-subtle">
  <NavbarBrand>Member Dashboard</NavbarBrand>
  <Nav navbar>
  <NavItem>
    <div class="d-flex flex-row">
      {p.fullname} ({p.email}, {p.neon_id})
  	  <NavLink href="/logout">Logout</NavLink>
    </div>
  </NavItem>
  </Nav>
</Navbar>
<main>
  {#if show_discord_setup}
	<Card class="my-3">
	<CardHeader>
	<CardTitle>Discord Account</CardTitle>
	</CardHeader>
	<CardBody>
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
  {/if}

  <Card class="my-3">
	<CardHeader>
	<CardTitle>Links</CardTitle>
	</CardHeader>
	<CardBody>
    <ListGroup>
      <ListGroupItem><a href="/events" target="_blank">Events and Reservations</a></ListGroupItem>
    {#if match(["Instructor", "Private Instructor"], p.roles)}
      <ListGroupItem>
        <a href="/instructor" target="_blank">Instructor Dashboard</a>
      </ListGroupItem>
    {/if}
    {#if match(["Shop Tech", "Shop Tech Lead"], p.roles) }
      <ListGroupItem><a href="/techs" target="_blank">Shop Tech Dashboard</a></ListGroupItem>
    {/if}
    {#if match(["Board Member", "Staff"], p.roles)}
      <ListGroupItem><a href="/staff" target="_blank">Discord Summarizer</a></ListGroupItem>
    {/if}
    </ListGroup>
  </CardBody>
  </Card>

  <Card class="my-3">
	<CardHeader>
	<CardTitle>Clearances</CardTitle>
	</CardHeader>
  <CardBody>
    {#if p.clearances.length == 0}
      <p>Looks like you don't have any equipment clearances yet.</p>
      <p>Why not <a href="https://protohaven.org/classes" target="_blank">take a class?</a></p>
    {/if}
    {#each p.clearances as c}
      <Badge color="light">{c}</Badge>
    {/each}
  </CardBody>
  </Card>
</main>
{:catch error}
  <FetchError {error}/>
{/await}

<style>
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
