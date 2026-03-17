<script type="typescript">

import '../../app.scss';
import { onMount } from 'svelte';
import {get, post} from '$lib/api.ts';

import { Card, CardHeader, CardTitle, CardBody, Container, Row, Col, Navbar, NavbarBrand, Nav, NavItem, NavLink, Spinner } from '@sveltestrap/sveltestrap';
import ClassDetails from '$lib/instructor/class_details.svelte';
import Profile from '$lib/instructor/profile.svelte';
import Scheduler from '$lib/instructor/scheduler.svelte';
import InstructorList from '$lib/instructor/instructor_list.svelte';
import ClassTemplates from '$lib/instructor/class_templates.svelte';
import FetchError from '$lib/fetch_error.svelte';


let start = new Date();
start.setDate(start.getDate() + 14);
start = start.toJSON().slice(0, 10);
let end = new Date();
end.setDate(end.getDate() + 40);
end = end.toJSON().slice(0,10);
let promise = new Promise((resolve,reject) => {});
let admin = false;
let user;
let activeTab;
onMount(() => {
  activeTab = (window.location.hash || "#profile").substring(1).trim();
  const urlParams = new URLSearchParams(window.location.search);
  let e = urlParams.get("email");
  console.log(`E is ${e}`);
	promise = get("/whoami").then((d) => {
      admin = (d.roles || []).some(role =>
        ["Education Lead", "Admin", "Board Member", "Staff"].includes(role)
      );
      console.log(d)
      user=d;
      if (!e) {
        promise = Promise.resolve(d);
        fetch_instructor_profile(d.email);
      } else {
        promise = Promise.resolve({email: e});
        fetch_instructor_profile(e);
      }
      return d;
    });
});

function on_tab(e) {
  activeTab = e.target.href.split("#")[1] || "profile";
  window.location.hash = activeTab;
  console.log("activeTab", activeTab);
}

let profile = null;
let templates = null;
function fetch_instructor_profile(email) {
  const url = "/instructor/about?email=" + encodeURIComponent(email);
  console.log(`getting profile data for email ${email} -> ${url}`);
  profile = get(url).then((result) =>{
    console.log("Instructor profile:", result);
    console.log("Seeking templates for classes:", result.classes);
    templates = get("/instructor/class/templates?ids=" + encodeURIComponent(Object.keys(result.classes)));
    return result;
  }).catch((e) => {
      console.log(e);
      throw e;
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
    <NavItem>
    {#await promise}
      <Spinner/>
    {:then}
      {#if !user || !user.fullname}
        <NavLink href="http://api.protohaven.org/login?referrer=/techs">Login</NavLink>
      {:else}
        <NavLink href="/logout">{user.fullname} (Logout)</NavLink>
      {/if}
    {/await}
    </NavItem>
  </Nav>
</Navbar>
<!-- Note: Nav is used here instead of Tabs directly because Tabs does not
     support URL anchor based routing - see
     https://github.com/sveltestrap/sveltestrap/issues/82 -->
<Nav tabs>
  <NavItem><NavLink href="#profile" on:click={on_tab}>Profile</NavLink></NavItem>
  <NavItem><NavLink href="#classes" on:click={on_tab}>Classes</NavLink></NavItem>
  {#if admin}
    <NavItem><NavLink href="#roster" on:click={on_tab}>Roster</NavLink></NavItem>
    <NavItem><NavLink href="#templates" on:click={on_tab}>Class Templates</NavLink></NavItem>
  {/if}
</Nav>
{#await promise}
  <Spinner/>
  <strong>Resolving instructor data...</strong>
{:then}
  <main>
    <Container>
    {#await profile}
      <Spinner/>
    {:then p}
    <Scheduler {admin} email={p.email} inst={fullname} classes={p.classes || {}} {templates} inst_id={airtable_id} bind:open={scheduler_open}/>

    <!-- Profile Tab -->
    {#if activeTab === 'profile'}
      <Profile {profile} on_scheduler={(fname, aid)=> {scheduler_open=true; fullname=fname; airtable_id=aid;}}/>
    {/if}

    <!-- Classes Tab -->
    {#if activeTab === 'classes'}
      <ClassDetails email={p.email} {scheduler_open}/>
    {/if}

    <!-- Roster Tab (Admin only) -->
    {#if admin && activeTab === 'roster'}
      <InstructorList {user} visible={activeTab === 'roster'}/>
    {/if}

    <!-- Class Templates Tab (Admin only) -->
    {#if admin && activeTab === 'templates'}
      <ClassTemplates visible={activeTab === 'templates'}/>
    {/if}

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
