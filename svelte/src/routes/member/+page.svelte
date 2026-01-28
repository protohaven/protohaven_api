<script type="typescript">
  import '../../app.scss';
  import { onMount } from 'svelte';
  import {get, post} from '$lib/api.ts';

  import FetchError from '$lib/fetch_error.svelte';
  import EventList from '$lib/member/event_list.svelte';
  import {Accordion, AccordionItem, Badge, Card, Spinner, ListGroup, ListGroupItem, CardTitle, CardSubtitle, CardHeader, CardBody, CardFooter, Button, Input, Navbar, NavbarBrand, Nav, NavItem, NavLink } from '@sveltestrap/sveltestrap';

  let first;
  let last;
  let discord_id;
  let show_discord_setup = false;
  let neon_id;

  let promise = new Promise(() => {});
  let recertPromise = new Promise(() => { return {pending: [], configs: []} });
  onMount(() => {
	  const urlParams = new URLSearchParams(window.location.search);
	  discord_id = urlParams.get("discord_id") || "";
    show_discord_setup = discord_id !== "";
	  neon_id = urlParams.get("neon_id") || null;
	  promise = get("/whoami");
    recertPromise = get("/member/recert_data")
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

  <Card class="my-3">
  <CardHeader>
        <CardTitle>Events</CardTitle>
  </CardHeader>
  <CardBody>
        <EventList/>
  </CardBody>
  </Card>

  <Card class="my-3">
  <CardHeader>
        <CardTitle>Recertification</CardTitle>
  </CardHeader>
  <CardBody>
    {#await recertPromise}
    <Spinner/>Loading...
    {:then rc}
          <h5 style="my-3">Pending Recertifications:</h5>
          <div>Recertification is a work in progress, estimated to roll out in 2026.</div>
          <div><strong>For more info on the recertification process, see <a href="https://wiki.protohaven.org/books/policies/page/tool-recertification" target="_blank">our wiki</a>.</strong></div>
          {#if rc.pending.length > 0}
          <em>Note: If you need to recertify multiple tools of the same type (e.g., Laser 1 and Laser 2), you may only need to take one quiz for all of them. This is typically indicated on the first page of the online quiz.</em>
          <ListGroup>
          {#each rc.pending as pend}
            <ListGroupItem color={(new Date(pend[1]) > new Date()) ? "warning" : "danger"}>
              <strong>{pend[2].tool_name}</strong> -
              {#if pend[2].quiz_url}<a href={pend[2].quiz_url} target="_blank">Quiz Needed</a>
              {:else}
                <a href="https://form.asana.com/?k=YXgO7epJe3brNGLS6sOw7A&d=1199692158232291" target="_blank">Instruction Needed</a>
              {/if}
              by {pend[1]}
            </ListGroupItem>
          {/each}
          </ListGroup>
          {:else}
            <p><em>No recertification needed at this time.</em></p>
          {/if}
          <br>
          <h5 style="my-3">All Tool Recertifications</h5>
          <Accordion stayOpen>
          <AccordionItem header="Click Here for All Tool Recertifications">
          <p><em>This page lists tools requiring recertification and their specific processes.</em></p>
          <p><em>Tool clearances are granted only after an instructor verifies safe usage through classes or private instruction. Quizzes serve for recertification only after initial clearance is earned.</em></p>
          {#each rc.configs as cfg}
            <Card style="my-3">
            <CardHeader><strong>{cfg.tool}: {cfg.tool_name}</strong></CardHeader>
            <CardBody>
            <p>Process: {cfg.humanized}</p>
            {#if cfg.quiz_url}
            <p>Quiz URL: <a href={cfg.quiz_url} target="_blank">Click Here</a></p>
            {/if}
            </CardBody>
            </Card>
          {/each}
          </AccordionItem>
          </Accordion>
    {/await}
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
