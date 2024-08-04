<script type="ts">

import '../../app.scss';
import { onMount } from 'svelte';
import {get, post} from '$lib/api.ts';

import { Container, Row, Col, Navbar, NavbarBrand, Spinner } from '@sveltestrap/sveltestrap';
import Calendar from '$lib/dashboard/calendar.svelte';
import ClassDetails from '$lib/dashboard/class_details.svelte';
import Profile from '$lib/dashboard/profile.svelte';
import Scheduler from '$lib/dashboard/scheduler.svelte';
import FetchError from '$lib/fetch_error.svelte';


let start = new Date();
start.setDate(start.getDate() + 14);
start = start.toJSON().slice(0, 10);
let end = new Date();
end.setDate(end.getDate() + 40);
end = end.toJSON().slice(0,10);
let promise = new Promise((resolve,reject)=>{});
onMount(() => {

  const urlParams = new URLSearchParams(window.location.search);
  let e= urlParams.get("email");
  if (!e) {
	promise = get("/whoami").then((data) => data.email);
  } else {
    promise = Promise.resolve(e);
  }
});

let scheduler_open = false;
let fullname = "";
let airtable_id = "";
</script>

<Navbar color="primary-subtle">
  <NavbarBrand>Instructor Dashboard</NavbarBrand>
</Navbar>
<main>
  {#await promise}
    <Spinner/>
    <h3>Resolving instructor data...</h3>
  {:then email}
  <Scheduler {email} inst={fullname} inst_id={airtable_id} bind:open={scheduler_open}/>
  <Container>
  <Row>
  <Col>
    <Profile {email} on_scheduler={(fname, aid)=> {scheduler_open=true; fullname=fname; airtable_id=aid;}}/>
  </Col>
  <Col>
    <ClassDetails {email} {scheduler_open}/>
  </Col>
  </Row>
  </Container>
  {:catch error}
    <FetchError {error}/>
  {/await}
</main>

<style>
main {
  width: 100%;
  padding: 15px;
  margin: 0 auto;
  display: flex;
  flex-direction: row;
  justify-content: center;
  align-items: flex-start;
}
</style>
