<script type="ts">

import '../app.scss';
import { onMount } from 'svelte';

import { Navbar, NavbarBrand } from '@sveltestrap/sveltestrap';
import ClassDetails from '$lib/class_details.svelte';
import Profile from '$lib/profile.svelte';

let email;
let base_url = "http://localhost:5000";
onMount(() => {
  if (window.location.href.indexOf("localhost") === -1) {
  base_url = "http://api.protohaven.org";
  }

  const urlParams = new URLSearchParams(window.location.search);
  email = urlParams.get("email");
});

</script>

<Navbar color="primary-subtle">
  <NavbarBrand>Instructor Dashboard</NavbarBrand>
</Navbar>
<main>
  {#if email}
  <Profile {base_url} {email}/>
  <ClassDetails {base_url} {email}/>
  {/if}
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
