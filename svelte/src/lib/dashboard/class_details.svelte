<script type="ts">

import {onMount} from 'svelte';
import { Table, Button, Row, Col, Card, CardHeader, CardTitle, CardSubtitle, CardText, Icon, CardFooter, CardBody, Input, Spinner, FormGroup, Navbar, NavbarBrand, Nav, NavItem } from '@sveltestrap/sveltestrap';
import ClassCard from './class_card.svelte';

export let base_url;
let classes = [];
let readiness = {};
export let email;

let promise;
function refresh() {
  promise = fetch(base_url + "/instructor/class_details?email=" + email).then((rep) => rep.json()).then((data) => data.schedule);
}
onMount(refresh);

let show_proposed = true;

</script>

<div style="width: 40vw; margin-left: 20px;">

{#await promise}
<Spinner/>
{:then classes}
{#if classes }
  {#each classes as c}
    {#if !c['Rejected']}
    <ClassCard {base_url} eid={c[0]} c_init={c[1]}/>
    {/if}
  {/each}

  <Button on:click={refresh}><Icon name="arrow-clockwise"/>Refresh Class List</Button>

  {#if classes.length == 0}
    <em>No classes fond - contact education@protohaven.org or post to #instructors on Discord if you wish to schedule more.</em>
  {/if}
{:else}
  Loading...
{/if}
{:catch error}
	TODO error {error.message}
{/await}
</div>
