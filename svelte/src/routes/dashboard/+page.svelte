<script type="ts">

import '../../app.scss';
import { onMount } from 'svelte';
import {get, post} from '$lib/api.ts';

import { Navbar, NavbarBrand, Spinner } from '@sveltestrap/sveltestrap';
import ClassDetails from '$lib/dashboard/class_details.svelte';
import Profile from '$lib/dashboard/profile.svelte';
import Scheduler from '$lib/dashboard/scheduler.svelte';
import FetchError from '$lib/dashboard/fetch_error.svelte';

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
</script>

<Navbar color="primary-subtle">
  <NavbarBrand>Instructor Dashboard</NavbarBrand>
</Navbar>
<main>
  {#await promise}
    <Spinner/>
    <h3>Resolving instructor data...</h3>
  {:then email}
  <div>
    <Profile {email} on_scheduler={(fname)=> {scheduler_open=true; fullname=fname;}}/>
    <Scheduler {email} inst={fullname} bind:open={scheduler_open}/>
  </div>
  <ClassDetails {email} {scheduler_open}/>
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
