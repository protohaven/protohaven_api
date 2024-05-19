<script type="ts">
  import '../../app.scss';
  import { Spinner, Row, Card, Container, Navbar, NavbarBrand } from '@sveltestrap/sveltestrap';
  import TechsList from '$lib/techs/techs_list.svelte';
  import ToolState from '$lib/techs/tool_state.svelte';
  import Shifts from '$lib/techs/shifts.svelte';
  import AreaLeads from '$lib/techs/area_leads.svelte';
  import Forecast from '$lib/techs/forecast.svelte';
  import { onMount } from 'svelte';

  let promise = new Promise((resolve, reject) => {});
  onMount(() => {
    let base_url = "http://localhost:5000";
    if (window.location.href.indexOf("localhost") === -1) {
    let base_url = "https://api.protohaven.org";
    }
    promise = Promise.resolve(base_url);
  });

</script>


<Navbar color="secondary-subtle">
  <NavbarBrand>Techs Dashboard</NavbarBrand>
</Navbar>

<main>
{#await promise}
  <Spinner/>
{:then base_url}
  <ToolState/>
  <Shifts/>
  <Forecast/>
  <AreaLeads/>
  <TechsList {base_url}/>
{/await}
</main>


<style>
		main {
			width: 80vw;
			padding: 15px;
			margin: 0 auto;
			display: -ms-flexbox;
			display: -webkit-box;
			display: flex;
			flex-direction: column;
			-ms-flex-align: center;
			-ms-flex-pack: center;
			-webkit-box-align: center;
			align-items: center;
			-webkit-box-pack: center;
			justify-content: center;
			padding-top: 40px;
			padding-bottom: 40px;
  			background-color: #f8f8f8;
		}
</style>
