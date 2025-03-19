<script type="typescript">
  import '../../app.scss';
  import FetchError from '$lib/fetch_error.svelte';
  import { Spinner, Row, Card, Container, Navbar, NavItem, NavbarBrand, NavLink, Nav } from '@sveltestrap/sveltestrap';
  import {get} from '$lib/api.ts';
  import TechsList from '$lib/techs/techs_list.svelte';
  import ToolState from '$lib/techs/tool_state.svelte';
  import Shifts from '$lib/techs/shifts.svelte';
  import Members from '$lib/techs/members.svelte';
  import Assignments from '$lib/techs/assignments.svelte';
  import AreaLeads from '$lib/techs/area_leads.svelte';
  import Storage from '$lib/techs/storage.svelte';
  import Events from '$lib/techs/events.svelte';
  import { onMount } from 'svelte';

  let promise;
  let user;
  let activeTab;
  onMount(() => {
    activeTab = (window.location.hash || "#cal").substring(1).trim();
    console.log("active", activeTab);
    const urlParams = new URLSearchParams(window.location.search);
    let e= urlParams.get("email");
    if (!e) {
      promise = get("/whoami").then((d) => {
        user = d;
      }).catch((e) => {
        if (e.message.indexOf("You are not logged in") !== -1) {
	        return "";
        }
	      throw e;
      });
    }
  });
  function on_tab(e) {
    activeTab = e.target.href.split("#")[1] || "cal";
    window.location.hash = activeTab;
    console.log("activeTab", activeTab);
  }

</script>

<Navbar color="secondary-subtle" sticky="">
  <NavbarBrand>Techs Dashboard</NavbarBrand>
  <Nav>
    <NavItem>
      <NavLink href="/events" target="_blank">Events Dashboard</NavLink>
    </NavItem>
    <NavItem>
      <NavLink href="https://protohaven.org/maintenance" target="_blank">Tool Report</NavLink>
    </NavItem>
    <NavItem>
      <NavLink href="https://wiki.protohaven.org/shelves/shop-techs" target="_blank">Wiki</NavLink>
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
  <NavItem><NavLink href="#cal" on:click={on_tab}>Cal</NavLink></NavItem>
  <NavItem><NavLink href="#members" on:click={on_tab}>Members</NavLink></NavItem>
  <NavItem><NavLink href="#shifts" on:click={on_tab}>Shifts</NavLink></NavItem>
  <NavItem><NavLink href="#tools" on:click={on_tab}>Tools</NavLink></NavItem>
  <NavItem><NavLink href="#storage" on:click={on_tab}>Storage</NavLink></NavItem>
  <NavItem><NavLink href="#areas" on:click={on_tab}>Areas</NavLink></NavItem>
  <NavItem><NavLink href="#techs" on:click={on_tab}>Roster</NavLink></NavItem>
  <NavItem><NavLink href="#events" on:click={on_tab}>Events</NavLink></NavItem>
</Nav>
<Shifts {user} visible={activeTab == 'cal'}/>
<Members {user} visible={activeTab == 'members'}/>
<Assignments visible={activeTab == 'shifts'}/>
<ToolState visible={activeTab == 'tools'}/>
<Storage visible={activeTab == 'storage'}/>
<AreaLeads visible={activeTab == 'areas'}/>
<TechsList visible={activeTab === 'techs'}/>
<Events {user} visible={activeTab === 'events'}/>
{#await promise}
  <span></span>
{:catch error}
  <FetchError {error}/>
{/await}
