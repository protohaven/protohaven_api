<script type="ts">

import '../../app.scss';
import { onMount } from 'svelte';

import { Navbar, NavbarBrand, Spinner } from '@sveltestrap/sveltestrap';
import ClassDetails from '$lib/dashboard/class_details.svelte';
import Profile from '$lib/dashboard/profile.svelte';
import Scheduler from '$lib/dashboard/scheduler.svelte';
import FetchError from '$lib/dashboard/fetch_error.svelte';

let promise = new Promise((resolve,reject)=>{});
let base_url = "http://localhost:5000";
onMount(() => {
  if (window.location.href.indexOf("localhost") === -1) {
  base_url = "https://api.protohaven.org";
  }

  const urlParams = new URLSearchParams(window.location.search);
  let e= urlParams.get("email");
  if (!e) {
	promise = fetch(base_url + "/whoami").then((rep)=>rep.text())
  	.then((body) => {
	  try {
	  	return JSON.parse(body);
	  } catch (err) {
		throw Error(`Invalid reply from server: ${body}`);
	  }
	})
	.then((data) => data.email);
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
    <Profile {base_url} {email} on_scheduler={(fname)=> {scheduler_open=true; fullname=fname;}}/>
    <Scheduler {base_url} {email} inst={fullname} bind:open={scheduler_open}/>
  </div>
  <ClassDetails {base_url} {email} {scheduler_open}/>
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
