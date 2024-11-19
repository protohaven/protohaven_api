<script type="typescript">

import {onMount} from 'svelte';
import { Table, Accordion, AccordionItem, Button, Row, Container, Col, Card, CardHeader, CardTitle, Modal, CardSubtitle, CardText, Icon, Tooltip, CardFooter, CardBody, Input, Spinner, FormGroup, Navbar, NavbarBrand, Nav, NavItem, Toast, ToastBody, ToastHeader } from '@sveltestrap/sveltestrap';
import Editor from './forecast_override.svelte';
import Calendar from './calendar.svelte';
import FetchError from '../fetch_error.svelte';
import {get, post, isodate} from '$lib/api.ts';

export let user;
export let visible;
let loaded = false;
let promise = new Promise((resolve) => {calendar_view: [{
  filler: false,
  date: "2024-12-01",
  techs: ["a", "b"],
  edited: false,
}]});
function refresh() {
  promise = get("/techs/forecast").then((data) => {
    loaded = true;

    // Left pad data until we hit a Sunday
    if (!data.calendar_view) {
      return [];
    }
    const cal = data.calendar_view;
    let d = new Date(cal[0].date);
    while (d.getUTCDay() !== 0) {
      d.setDate(d.getDate() - 1);
      cal.unshift({date: isodate(d), filler: true});
    }
    d = new Date(cal[cal.length-1].date);
    while (d.getUTCDay() !== 6) {
      d.setDate(d.getDate() + 1);
      cal.push({date: isodate(d), filler: true});
    }
    return cal;
  });
}
$: {
  if (visible && !loaded) {
    refresh();
  }
}

let edit = null;

function start_edit(s, ap) {
 let e = {ap: ap, date: s.date, techs: s.people, ...user};
 if (s.ovr) {
   e = {...e, id: s.ovr.id, orig: s.ovr.orig, editor: s.ovr.editor};
 }
  edit = e;
}

</script>

<style>
.calendar {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
}
.header {
  text-align: center;
}
.filler {
  background-color: #EEE;
}
</style>

{#if visible}
<Card>
  <CardHeader>
  <CardTitle>Calendar</CardTitle>
  <p>An editable forecast of upcoming shifts.</p>
  </CardHeader>
<CardBody>
{#await promise}
	<Spinner/>Loading...
{:then p}
  <div class="calendar">
  <div class="header">Sun</div>
  <div class="header">Mon</div>
  <div class="header">Tue</div>
  <div class="header">Wed</div>
  <div class="header">Thu</div>
  <div class="header">Fri</div>
  <div class="header">Sat</div>
	{#each p as v}
  {#if v.filler}
    <div class="filler"></div>
  {:else}
    <Card class="day">
      <CardHeader><CardTitle>{v.date}</CardTitle></CardHeader>
      <CardBody>
      {#each ["AM", "PM"] as ap}
      <h5>{ap}</h5>
      <Button id={v[ap].id} class="p-2 mx-2" color={v[ap].color} on:click={() => start_edit(v, ap)}>
      {#if v[ap].ovr}*{/if}
      {#if v[ap].people.length === 0}
        Nobody on shift!
      {:else}
        {#each v[ap].people as ppl}<div>{ppl}</div>{/each}
      {/if}
      </Button>
      {/each}
      </CardBody>
    </Card>
  {/if}
  {/each}
  </div>
{:catch error}
  <FetchError {error}/>
{/await}
</CardBody>
<CardFooter>
  <p>
    Legend:
    <Button color='success'>3+ Techs</Button>
    <Button color='info'>2 Techs</Button>
    <Button color='warning'>1 Tech</Button>
    <Button color='danger'>0 Techs</Button>
  </p>
  <p><em>* indicates overridden shift info</em></p>
</CardFooter>
</Card>
{/if}

<Editor {edit} on_update={refresh}/>
