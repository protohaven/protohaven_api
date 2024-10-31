<script type="typescript">
  import '../../app.scss';
  import FetchError from '$lib/fetch_error.svelte';
  import { TabContent, TabPane, Spinner, Row, Card, Container, Navbar, NavItem, NavbarBrand, NavLink, Nav } from '@sveltestrap/sveltestrap';
  import {get} from '$lib/api.ts';
  import TechsList from '$lib/techs/techs_list.svelte';
  import ToolState from '$lib/techs/tool_state.svelte';
  import Shifts from '$lib/techs/shifts.svelte';
  import Assignments from '$lib/techs/assignments.svelte';
  import AreaLeads from '$lib/techs/area_leads.svelte';
  import Storage from '$lib/techs/storage.svelte';
  import Events from '$lib/techs/events.svelte';
  import { onMount } from 'svelte';

  let promise;
  let user;
  onMount(() => {
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
    } else {
      user = {email: e, fullname: 'Test User'};
      promise = Promise.resolve(user);
    }
  });

</script>

<Navbar color="secondary-subtle" sticky="">
  <NavbarBrand>Techs Dashboard</NavbarBrand>
  <Nav navbar>
    <NavItem>
    {#await promise}
      <Spinner/>
    {:then}
      {#if !user || !user.fullname}
        <a href="http://api.protohaven.org/login?referrer=/techs">Login</a>
      {:else}
        {user.fullname} (<a href="/logout">Logout</a>)
      {/if}
    {/await}
    </NavItem>
  </Nav>
</Navbar>
<TabContent>
  <!--Note: TabPanes are listed here instead of within the sub-components because
      they are rendered twice inside of TabContent - once for the tab and once for
      the body. This would cause multiple onMount() executions and double the number
      of requests to the server.-->
  <TabPane tabId="schedule" tab="Cal" active>
  <Shifts {user}/>
  </TabPane>
  <TabPane tabId="assignments" tab="Shifts" active>
    <Assignments/>
  </TabPane>
  <TabPane tabId="tools" tab="Tools">
    <ToolState/>
  </TabPane>
  <TabPane tabId="storage" tab="Storage">
    <Storage/>
  </TabPane>
  <TabPane tabId="area_leads" tab="Areas">
    <AreaLeads/>
  </TabPane>
  <TabPane tabId="techs" tab="Techs">
    <TechsList/>
  </TabPane>
  <TabPane tabId="events" tab="Events">
    <Events {user}/>
  </TabPane>
</TabContent>
{#await promise}
  <span></span>
{:catch error}
  <FetchError {error}/>
{/await}
