<script type="typescript">

import '../../app.scss';
import { onMount } from 'svelte';
import {get, post} from '$lib/api.ts';

import { Card, CardHeader, CardTitle, CardBody, Container, Row, Col, Navbar, NavbarBrand, Nav, NavItem, NavLink, Spinner } from '@sveltestrap/sveltestrap';
import Calendar from '$lib/instructor/calendar.svelte';
import ClassDetails from '$lib/instructor/class_details.svelte';
import Profile from '$lib/instructor/profile.svelte';
import Scheduler from '$lib/instructor/scheduler.svelte';
import AdminPanel from '$lib/instructor/admin_panel.svelte';
import FetchError from '$lib/fetch_error.svelte';


let start = new Date();
start.setDate(start.getDate() + 14);
start = start.toJSON().slice(0, 10);
let end = new Date();
end.setDate(end.getDate() + 40);
end = end.toJSON().slice(0,10);
let promise = new Promise((resolve,reject) => {});
let admin = false;
onMount(() => {
  const urlParams = new URLSearchParams(window.location.search);
  let e = urlParams.get("email");
  console.log(`E is ${e}`);
  if (!e) {
	  promise = get("/whoami").then((d) => {
      admin = (d.roles || []).indexOf("Education Lead") !== -1;
      fetch_instructor_profile(d.email);
      return d;
    });
  } else {
    promise = Promise.resolve({email: e});
    fetch_instructor_profile(e);
  }
});


let profile = null;
let templates = null;
function fetch_instructor_profile(email) {
  const url = "/instructor/about?email=" + encodeURIComponent(email);
  console.log(`getting profile data for email ${email} -> ${url}`);
  profile = get(url).then((result) =>{
    console.log("Instructor profile:", result);
    templates = get("/instructor/class/templates?ids=" + encodeURIComponent(Object.keys(result.classes)));
    return result;
  });
}

let scheduler_open = false;
let fullname = "";
let airtable_id = "";
</script>

<Navbar color="primary-subtle" sticky="">
  <NavbarBrand>Instructor Dashboard</NavbarBrand>
  <Nav>
    <NavItem>
      <NavLink href="https://docs.google.com/forms/d/e/1FAIpQLScX3HbZJ1-Fm_XPufidvleu6iLWvMCASZ4rc8rPYcwu_G33gg/viewform" target="_blank">Log Form (Blank)</NavLink>
    </NavItem>
    <NavItem>
      <NavLink href="https://wiki.protohaven.org/books/instructors-handbook" target="_blank">Wiki/Help</NavLink>
    </NavItem>
  </Nav>
</Navbar>
{#await promise}
  <Spinner/>
  <strong>Resolving instructor data...</strong>
{:then p}
  {#if admin}
    <AdminPanel/>
  {/if}
  <main>
    <Container>
    {#await profile}
      <Spinner/>
    {:then p}
    <Scheduler email={p.email} inst={fullname} classes={p.classes || {}} {templates} inst_id={airtable_id} bind:open={scheduler_open}/>
    
    <Row>
    <Col>
      <Profile {profile} on_scheduler={(fname, aid)=> {scheduler_open=true; fullname=fname; airtable_id=aid;}}/>
    </Col>
    <Col>
      <ClassDetails email={p.email} {scheduler_open}/>
    </Col>
    </Row>
    {:catch error}
        <FetchError {error}/>
    {/await}
    </Container>
  </main>
{:catch error}
  <FetchError {error}/>
{/await}

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
