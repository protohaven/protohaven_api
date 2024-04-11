<script type="ts">
  import '../../app.scss';
  import { Row, Card, Container, Navbar, NavbarBrand } from '@sveltestrap/sveltestrap';
  import TechsList from '$lib/tech_lead/techs_list.svelte';
  import { onMount } from 'svelte';

  let base_url = "http://localhost:5000";
  onMount(() => {
    if (window.location.href.indexOf("localhost") === -1) {
    base_url = "http://api.protohaven.org";
    }
  });

</script>


<Navbar color="secondary-subtle">
  <NavbarBrand>Tech Lead Dashboard</NavbarBrand>
</Navbar>

<main>
  <TechsList {base_url}/>
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
