<script type="ts">

  import '../../app.scss';
  import {get, post} from '$lib/api.ts';
  import { Row, Col, Card, Container, Spinner } from '@sveltestrap/sveltestrap';
  import { onMount } from 'svelte';
  import ClassCard from '$lib/classes/class_card.svelte';

  let base_url = "http://localhost:5000";
  let promise = Promise.resolve(null);
  onMount(() => {
    if (window.location.href.indexOf("localhost") === -1) {
    base_url = "https://api.protohaven.org";
    }
    promise = get("/class_listing").then((data) => {
      console.log(data);
      let date_bounded = [];
      let day = null;
      let acc = [];
      for (let c of data) {
	if (c['name'].indexOf("New Member Orientation") !== -1 || c['name'].indexOf("Private Instruction") !== -1) {
	  continue;
	}
	acc.push(c);
      }
      return acc;
    });
  });
</script>

<main>
{#await promise}
	<Spinner/>
{:then result}
	{#if result}
	  <Container>
	    <Row cols={{ lg: 3, md: 2, sm: 1 }}>
	      {#each result as c}
	      <Col>
		  <ClassCard {c}/>
	      </Col>
	      {/each}
	    </Row>
	  </Container>
	{:else}
		<Spinner/>
	{/if}
{:catch error}
  TODO error {error.message}
{/await}
</main>

<style>
		main {
			width: 100%;
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
