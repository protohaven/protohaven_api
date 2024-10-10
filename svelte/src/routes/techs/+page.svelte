<script type="typescript">
  import '../../app.scss';
  import FetchError from '$lib/fetch_error.svelte';
  import { TabContent, Spinner, Row, Card, Container, Navbar, NavItem, NavbarBrand, NavLink, Nav } from '@sveltestrap/sveltestrap';
  import {get} from '$lib/api.ts';
  import TechsList from '$lib/techs/techs_list.svelte';
  import ToolState from '$lib/techs/tool_state.svelte';
  import Shifts from '$lib/techs/shifts.svelte';
  import Assignments from '$lib/techs/assignments.svelte';
  import AreaLeads from '$lib/techs/area_leads.svelte';
  import Storage from '$lib/techs/storage.svelte';
  import { onMount } from 'svelte';

  let promise = new Promise((resolve, reject) => {});
  onMount(() => {
    const urlParams = new URLSearchParams(window.location.search);
    let e= urlParams.get("email");
    if (!e) {
      promise = get("/whoami").catch((e) => {
        if (e.message.indexOf("You are not logged in") !== -1) {
	  return "";
        }
	throw e;
      });
    } else {
      promise = Promise.resolve({email: e, fullname: 'Test User'});
    }
  });

</script>

{#await promise}
  <Spinner/>
{:then user}
<Navbar color="secondary-subtle" sticky="">
  <NavbarBrand>Techs Dashboard</NavbarBrand>
  <Nav navbar>
    <NavItem>
    {#if !user}
      <a href="/login?referrer=/techs">Login</a>
    {:else}
      {user.fullname} (<a href="/logout">Logout</a>)
    {/if}
    </NavItem>
  </Nav>
</Navbar>
<TabContent>
  <Shifts {user}/>
  <Assignments/>
  <ToolState/>
  <Storage/>
  <AreaLeads/>
  <TechsList/>
</TabContent>
{:catch error}
  <FetchError {error}/>
{/await}
