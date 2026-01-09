<script>
  import '../../app.scss';
  import { Spinner, Row, Card, Container, Navbar, NavItem, NavbarBrand, NavLink, Nav } from '@sveltestrap/sveltestrap';
  import SummarizeDiscord from '$lib/staff/summarize_discord.svelte';
  import { onMount } from 'svelte';
  import {get} from '$lib/api.ts';
  import OpsReport from '$lib/staff/ops_report.svelte';

  let activeTab;
  let user;
  let promise;
  onMount(() => {
    activeTab = (window.location.hash || "#summary").substring(1).trim();
    console.log("active", activeTab);
    promise = get("/whoami").then((d) => {
      user = d;
    }).catch((e) => {
      if (e.message.indexOf("You are not logged in") !== -1) {
        return "";
      }
      throw e;
    });
  });
  function on_tab(e) {
    activeTab = e.target.href.split("#")[1] || "summary";
    window.location.hash = activeTab;
    console.log("activeTab", activeTab);
  }

</script>

<Navbar color="primary-subtle" sticky="">
  <NavbarBrand>Staff Dashboard</NavbarBrand>
  <Nav>
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

<Nav tabs>
  <NavItem><NavLink href="#summary" on:click={on_tab}>Discord Summary</NavLink></NavItem>
  <NavItem><NavLink href="#opsreport" on:click={on_tab}>Ops Report</NavLink></NavItem>
</Nav>
<SummarizeDiscord {user} visible={activeTab == 'summary'} {user}/>
<OpsReport visible={activeTab == 'opsreport'} {user}/>
