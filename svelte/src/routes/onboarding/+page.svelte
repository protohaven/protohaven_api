<script type="ts">
  import '../../app.scss';
  import FetchError from '$lib/fetch_error.svelte';
  import { onMount } from 'svelte';
  import { Alert, Accordion, AccordionItem, ListGroup, ListGroupItem, Image, FormGroup, Label, Spinner, Input, Button, Row, Card, CardFooter, CardHeader, CardTitle, CardBody, Container, Navbar, NavItem, NavbarBrand, NavLink, Nav } from '@sveltestrap/sveltestrap';
  import {get, post} from '$lib/api.ts';


  let onboarders = new Promise((r) => r([]));
  let assignable_roles = new Promise((r) => r([]));
  let fields = {'email': '', 'membership': []};
  onMount(() => {
	  for (let id of Object.keys(fields)) {
	  	console.log("fetch field", id);
		  fields[id] = localStorage.getItem("onboarding." + id, "") || fields[id];
	  }
	  fields.membership = [];
	  console.log("Now", fields);

	  onboarders = get('/onboarding/onboarders');
    assignable_roles = get('/onboarding/role_assignment');
  });

  function save() {
    for (let id of Object.keys(fields)) {
      localStorage.setItem("onboarding." + id, fields[id]);
    }
    console.log("fields saved:", fields);
  }


  let membership_promise;
  let email_feedback;
  let presubmit = true;
  function check_membership() {
    email_feedback = null;
    if (!fields.email) {
	email_feedback = "You must enter an email address to check membership";
	return;
    }
    presubmit = false;
    membership_promise = get(`/onboarding/check_membership?email=${fields.email}`)
          .then(function(membership) {
	        fields = {...fields, membership};
		save();
		return fields;
          });
  }


  let discord_promise = new Promise((r,_) => r());
  let discord_feedback = [];
  let discord_submitting = false;
  function discord_member_submit(m) {
    discord_feedback = [];
    if (!m.discord_user) {
      discord_feedback.push("Please Input a discord user");
    }
    if (!m.neon_id) {
      discord_feedback.push("Neon ID is required");
    }
    if (!m.first || !m.last) {
      discord_feedback.push("Full name must be fetched from Neon");
    }
    if (discord_feedback.length > 0) {
	return;
    }
    discord_submitting = true;
    discord_promise = get(`/onboarding/discord_member_add?name=${m.discord_user}&neon_id=${m.neon_id}&nick=${m.first}%20${m.last}`).finally(() => discord_submitting=false);
  }


  let roles_submitting = false;
  let roles_promise = new Promise((r,_) => r());
  function submit_roles(m) {
    roles_submitting = true;
    roles_promise = post('/onboarding/role_assignment', {email: fields.email, roles: m.roles}).finally(() => roles_submitting = false);
  }

  let coupon_promise = new Promise((r,_) => r());
  let creating = false;
  let coupon_feedback
  function create_coupon() {
    if (!fields.email) {
	coupon_promise = new Promise(() => {
		throw Error("Coupon creation requires an email address")
	});
	return;
    }
    creating = true;
    coupon_promise = get(`/onboarding/coupon?email=${fields.email}`).finally(() => creating = false);
  }
</script>


<Navbar><NavbarBrand><Image style="max-height:80px" src="logo_color.svg"></Image></NavbarBrand></Navbar>

<Container class="content">

<Card class="my-5">
	<CardHeader><CardTitle>Membership Check</CardTitle></CardHeader>
	<CardBody>
	<FormGroup>
		<Label>Email:</Label>
		<Input type="email" bind:value={fields.email} invalid={email_feedback} feedback={email_feedback}/>
	</FormGroup>
	</CardBody>
	<CardFooter>
		<Button on:click={check_membership}>Check</Button>
		<em>Membership data will be loaded if they're present in Neon.</em>
	</CardFooter>
</Card>

{#await membership_promise}
<Spinner/>
{:then p}
{#if !presubmit}
<Card class="my-5">
	<CardHeader><CardTitle>Found {fields.membership.length} Membership(s)</CardTitle></CardHeader>
	{#each fields.membership as m}
 	<ListGroup class="my-1">
		<ListGroupItem><strong>Neon ID:</strong> {m.neon_id}</ListGroupItem>
		<ListGroupItem><strong>Full Name:</strong> {m.first} {m.last}</ListGroupItem>
		<ListGroupItem><strong>Membership:</strong> {m.level}</ListGroupItem>
		<ListGroupItem><strong>Status:</strong> {m.status}</ListGroupItem>
		<ListGroupItem><strong>Roles:</strong> {m.roles}</ListGroupItem>
	</ListGroup>
	{/each}
</Card>
{/if}

{#if fields.membership.length > 0}
<Card class="my-5">
	<CardHeader><CardTitle>Discord connection</CardTitle></CardHeader>
	<CardBody>
	<p>Make sure discord is installed on their phone, then have them scan this QR code (tap bottom right profile button, scroll to "Scan QR Code"):</p>
	<Image style="height: 256px; width: 256px" src="join_discord.png"></Image>
	<p>
	Or they can go to <a href="https://protohaven.org/discord">protohaven.org/discord</a> in a web browser.
	</p>
	<h2>Discord role, name, and Neon association</h2>
	<p>This automation does the following:</p>
	<ul>
	<li>Grants the Members role to the member's discord user so they can see all the member channels</li>
	<li>Associates their discord user ID into Neon, so we can later automatically manage their roles and name</li>
	<li>Sets their display name (nickname) on the server to their full name (using the Input field above)</li>
	</ul>
	<p>You can run this multiple times on the same user without causing problems</p>

	{#each fields.membership as m}
		<FormGroup>
			<Label>Discord User for {m.first} {m.last} (#{m.neon_id}):</Label>
			<div class="d-flex flex-row">
				<Input type="text" bind:value={m.discord_user}></Input>
				<Button on:click={() => discord_member_submit(m)} disabled={discord_submitting}>Setup</Button>
			</div>
		</FormGroup>
	{/each}
	{#each discord_feedback as df}
		<Alert color="warning">{df}</Alert>
	{/each}
	{#await discord_promise}
	<Spinner/>
	{:then d}
	{#if d}{d.status}{/if}
	{:catch error}
	  <FetchError {error} nohelp/>
	{/await}
	</CardBody>
</Card>
{/if}

{:catch error}
  <FetchError {error} nohelp/>
{/await}

{#if fields.membership.length > 0}
<Card class="my-5">
<CardHeader><CardTitle>Role Assignment</CardTitle></CardHeader>
<CardBody>
<p>Roles determine what channels are visible in Discord, and which internal pages can be accessed or modified. For regular and AMP members, you can ignore this.</p>
{#await assignable_roles}
	<Spinner/>
{:then p}
	{#each fields.membership as m}
		<FormGroup>
			<Label>Roles for {m.first} {m.last} (#{m.neon_id}):</Label>
      {#each p as rolename}
        <Input type="checkbox" label={rolename} bind:checked={m.roles[rolename]}></Input>
      {/each}
      <Button on:click={() => submit_roles(m)} disabled={roles_submitting}>Apply</Button>
		</FormGroup>
	{/each}
{:catch error}
	<FetchError {error} nohelp/>
{/await}

{#await roles_promise}
	<Spinner/> <em>Updating roles can take up to 2 minutes.</em>
{:then r}
{#if r}
	{r.status}
{/if}
{:catch error}
	<FetchError {error} nohelp/>
{/await}
</CardBody>
</Card>
{/if}


<Card class="my-5">
<CardHeader><CardTitle>Coupon creator</CardTitle></CardHeader>
<CardBody>
<Button on:click={create_coupon} disabled={creating}>Create coupon</Button>
{#await coupon_promise}
	<Spinner/>
{:then p}
{#if p}
	{p.coupon}
{/if}
{:catch error}
	<FetchError {error} nohelp/>
{/await}
</CardBody>
</Card>


<Card class="my-5">
<CardHeader><CardTitle>Private Instruction</CardTitle></CardHeader>
<CardBody>

	<p>When done with private instruction, be sure they submit payment via <a target="_blank" href="https://protohaven.app.neoncrm.com/np/clients/protohaven/event.jsp?event=17631">Event Registration</a></p>

	<p>To log their clearance and get paid for your instruction, <a href="https://docs.google.com/forms/d/1iYDI2E0SKsCK-kNm6HtjiIzKm_5VXkgIXfK-0fjKVbI/edit" target="_blank">submit your log</a>.</p>

	<Accordion>
	<AccordionItem header="List of Onboarders">
	{#await onboarders}
		<Spinner/>
	{:then mm}
	  <ListGroup>
	  {#each mm as m}
		<ListGroupItem>
		  {m['First Name']} {m['Last Name']} (#{m['Account ID']}, {m['Email 1']})
		</ListGroupItem>
	  {/each}
	  </ListGroup>
	{:catch error}
		<FetchError {error} nohelp/>
	{/await}
	</AccordionItem>
	</Accordion>

</CardBody>
</Card>
</Container>
