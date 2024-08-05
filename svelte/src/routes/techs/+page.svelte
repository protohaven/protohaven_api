<script type="ts">
  import '../../app.scss';
  import FetchError from '$lib/fetch_error.svelte';
  import { Spinner, Row, Card, Container, Navbar, NavItem, NavbarBrand, NavLink, Nav } from '@sveltestrap/sveltestrap';
  import {get} from '$lib/api.ts';
  import TechsList from '$lib/techs/techs_list.svelte';
  import ToolState from '$lib/techs/tool_state.svelte';
  import Shifts from '$lib/techs/shifts.svelte';
  import AreaLeads from '$lib/techs/area_leads.svelte';
  import Forecast from '$lib/techs/forecast.svelte';
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
<Navbar color="secondary-subtle">
  <NavbarBrand>
  Techs Dashboard
  </NavbarBrand>
  <Nav navbar>
  <NavItem>
  {#if !user}
  	<NavLink href="/login?referrer=/techs">Login</NavLink>
  {:else}
    <div class="d-flex flex-row">
        {user.fullname} ({user.email})
  	<NavLink href="/logout">Logout</NavLink>
    </div>
  {/if}
  </NavItem>
  </Nav>
</Navbar>
  <ToolState/>
  <Shifts/>
  <Forecast {user}/>
  <AreaLeads/>
  <TechsList/>
{:catch error}
  <FetchError {error}/>
{/await}
