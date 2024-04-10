<script type="ts">
  import { Button, Icon, Image, Card, CardHeader, CardTitle, CardSubtitle, CardText, CardBody, CardFooter, Spinner, ListGroup, ListGroupItem, Alert } from '@sveltestrap/sveltestrap';
  import { onMount } from 'svelte';

  export let base_url;
  export let email;
  export let on_scheduler;

  let profile = null;
  let promise;
  function refresh() {
	promise = fetch(base_url + "/instructor/about?email=" + email).then((rep) => rep.json());
  }
  onMount(refresh);


  function li_color(v) {
    v = v.toLowerCase();
    let has_ok = v.indexOf("ok") !== -1;
    if (has_ok) {
      return "light";
    }
    return "warning";
  }
  function onboarded(p) {
    for (let k of ['active_membership', 'capabilities_listed', 'paperwork', 'discord_user', 'in_calendar']) {
      if (li_color(p[k]) == "warning") {
	return false;
      }
    }
    return true;
  }
</script>

<Card style="width: 20vw;">
{#await promise}
	<CardHeader>
		<CardTitle>Loading profile...</CardTitle>
	</CardHeader>
	<CardBody><Spinner></Spinner></CardBody>
{:then p}
{#if p !== undefined }
  <CardHeader>
    <CardTitle>
      <div>{p.fullname}</div>
    </CardTitle>
  </CardHeader>
  <CardBody>
    {#if p.profile_img}
    <Image fluid alt="instructor profile pic" src={p.profile_img} class="px-5 py-3"/>
    {/if}
    {#if p.bio}
    <CardText>{p.bio}</CardText>
    {/if}
    <CardSubtitle>Status</CardSubtitle>
      <ListGroup>
	<ListGroupItem color={li_color(p.active_membership)}>Membership: {p.active_membership}</ListGroupItem>
	<ListGroupItem color={li_color(p.capabilities_listed)}>Capabilities: {p.capabilities_listed}</ListGroupItem>
	<ListGroupItem color={li_color(p.paperwork)}>Paperwork: {p.paperwork}</ListGroupItem>
	<ListGroupItem color={li_color(p.discord_user)}>Discord: {#if p.discord_user == "missing"}Missing{:else}OK{/if}</ListGroupItem>
	<ListGroupItem color={li_color(p.in_calendar)}>Availabity: {#if p.in_calendar == "OK"}OK{:else}MISSING{/if} (see <a href="https://calendar.google.com/calendar/u/1/r?cid=Y19hYjA0OGUyMTgwNWEwYjVmN2YwOTRhODFmNmRiZDE5YTNjYmE1NTY1YjQwODk2MjU2NTY3OWNkNDhmZmQwMmQ5QGdyb3VwLmNhbGVuZGFyLmdvb2dsZS5jb20" target="_blank">Calendar</a>)</ListGroupItem>
      </ListGroup>
    {#if !onboarded(p) }
    <Alert color="warning" class="m-3">
      <strong>Your status is incomplete. Click <a href="https://protohaven.org/wiki/instructors#onboarding" target="_blank">HERE</a> for required instructor setup steps.</strong>
    </Alert>
    {/if}
  </CardBody>
  <CardFooter class="d-flex justify-content-end">
      <Button on:click={refresh}><Icon class="ml-auto" name="arrow-clockwise"/></Button>
      <Button on:click={on_scheduler}>Schedule more classes</Button>
  </CardFooter>
{:else}
	Loading...
{/if}
{:catch error}
	<CardHeader color="danger">
		<CardTitle>Error</CardTitle>
	</CardHeader>
	<CardBody>
		<CardText>{error.message}</CardText>
	</CardBody>
{/await}
</Card>
