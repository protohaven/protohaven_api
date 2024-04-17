<script type="ts">

import '../../app.scss';
import { onMount } from 'svelte';

import { Navbar, NavbarBrand, Spinner } from '@sveltestrap/sveltestrap';
import ClassDetails from '$lib/dashboard/class_details.svelte';
import Profile from '$lib/dashboard/profile.svelte';
import Scheduler from '$lib/dashboard/scheduler.svelte';
import FetchError from '$lib/dashboard/fetch_error.svelte';

let promise;
let base_url = "http://localhost:5000";
onMount(() => {
  if (window.location.href.indexOf("localhost") === -1) {
  base_url = "https://api.protohaven.org";
  }

  const urlParams = new URLSearchParams(window.location.search);
  let email = urlParams.get("email");
  if (!email) {
	promise = fetch(base_url + "/whoami").then((rep)=>rep.text())
  	.then((body) => {
	  try {
	  	return JSON.parse(body);
	  } catch (e) {
		throw Error(`Invalid reply from server: ${body}`);
	  }
	})
	.then((data) => data.email);
  } else {
    promise = Promise.resolve(email);
  }
});

let scheduler_open = false;
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
    <Profile {base_url} {email} on_scheduler={()=> scheduler_open=true}/>
    <Scheduler {base_url} {email} bind:open={scheduler_open}/>
  </div>
  <ClassDetails {base_url} {email}/>
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
