<script type="typescript">

import {onMount} from 'svelte';
import { Table, Label, Accordion, AccordionItem, Button, Row, Container, Col, Card, CardHeader, CardTitle, Modal, CardSubtitle, CardText, Icon, Tooltip, CardFooter, CardBody, Input, Spinner, FormGroup, Navbar, NavbarBrand, Nav, NavItem, Toast, ToastBody, ToastHeader } from '@sveltestrap/sveltestrap';
import Editor from './forecast_override.svelte';
import Calendar from './calendar.svelte';
import FetchError from '../fetch_error.svelte';
import {get, post, isodate} from '$lib/api.ts';

export let user;
export let visible;

const DEFAULT_DURATION = 14;
const DEFAULT_TRAIL = 3;

let start_date = new Date();
let end_date = new Date(start_date);
start_date.setDate(start_date.getDate() - DEFAULT_TRAIL);
start_date = isodate(start_date);
end_date.setDate(end_date.getDate() + DEFAULT_DURATION);
end_date = isodate(end_date);

function isToday(date) {
  let now = new Date();
  date = new Date(date);
  return now.getFullYear() === date.getFullYear() &&
         now.getMonth() === date.getMonth() &&
         now.getDate() === date.getDate();
}

function days_between(d1, d2) {
  // https://stackoverflow.com/a/2627493
  return Math.round(Math.abs((new Date(end_date) - new Date(start_date)) / (24*60*60*1000)));
}

let loaded = false;
let promise = new Promise((resolve) => {calendar_view: [{
  filler: false,
  date: "2024-12-01",
  techs: ["a", "b"],
  edited: false,
}]});
function refresh() {
  const diff_days = days_between(start_date, end_date) + 1; // Inclusive
  promise = get(`/techs/forecast?date=${isodate(start_date)}&days=${diff_days}`).then((data) => {
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
function date_changed(was_start) {
  console.log("date_changed");
  let fix = null;
  let start = new Date(start_date);
  let end = new Date(end_date);
  if (!end || end < start) {
    fix = DEFAULT_DURATION;
  } else if (days_between(start_date, end_date) > 60) {
    fix = 60;
  }

  if (fix) {
    console.log("fix", fix);
    if (was_start) {
      end_date = new Date(start_date);
      end_date.setDate(end_date.getDate() + fix);
      end_date = isodate(end_date);
    } else {
      start_date = new Date(end_date);
      start_date.setDate(start_date.getDate() - fix);
      start_date = isodate(start_date);
    }
  }
  refresh();
}
$: {
  if (visible && !loaded) {
    refresh();
  }
}

let edit = null;

function start_edit(s, ap) {
  console.log(s, ap);
 let e = {ap: ap, date: s.date, techs: s[ap].people, ...user};
 if (s[ap].ovr) {
   e = {...e, id: s[ap].ovr.id, orig: s[ap].ovr.orig, editor: s[ap].ovr.editor};
 }
 edit = e;
}

</script>

<style>
.calendar {
  display: grid;
  gap: 5px;
  grid-template-columns: repeat(7, 1fr);
  @media (max-width: 920px) {
    grid-template-columns: repeat(3, 1fr);
  }
}
.header {
  text-align: center;
  @media (max-width: 920px) {
    display: none;
  }
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
  <FormGroup>
    <Label>Start Date</Label>
    <Input type="date" bind:value={start_date} on:change={() => date_changed(true)}/>
  </FormGroup>
  <FormGroup>
    <Label>End Date</Label>
    <Input type="date" bind:value={end_date} on:change={() => date_changed(false)}/>
  </FormGroup>

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
    <Card class="day" style={isToday(v.date) ? "font-weight: bold;" : ""}>
      <div>{v.date}</div>
      <div class="my-2">
      {#each ["AM", "PM"] as ap}
      <div>{#if v[ap].ovr}*{/if}{ap}</div>
      <Button id={v[ap].id} class="p-2 mx-2" color={v[ap].color} on:click={() => start_edit(v, ap)}>
      {#if v[ap].people.length === 0}
        Nobody on shift!
      {:else}
        {#each v[ap].people as ppl}<div class="my-2">{ppl}</div>{/each}
      {/if}
      </Button>
      {/each}
      </div>
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
