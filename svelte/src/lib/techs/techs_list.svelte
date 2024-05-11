<script type="ts">

import {onMount} from 'svelte';
import { Table, Button, Row, Col, Card, CardHeader, Badge, CardTitle, Modal, CardSubtitle, CardText, Icon, Tooltip, CardFooter, CardBody, Input, Spinner, FormGroup, Navbar, NavbarBrand, Nav, NavItem, Toast, ToastBody, ToastHeader } from '@sveltestrap/sveltestrap';
import {get, post} from '$lib/api.ts';
import EditCell from './editable_td.svelte';


let promise = new Promise((resolve) => {});

let new_tech_email = "";
let shift_map = {};
let area_map = {};
let coverage_ok = [];
let coverage_missing = [];
let calendar_view = [];
let toast_msg = null;
let enrolling = false;
let tech_lead = false;

function refresh() {
  promise = get("/techs/all_status").then((data) => {
    shift_map = {};
    area_map = {};

    tech_lead = data.tech_lead;

    for (let t of data.techs) {
      if (!t['shift']) {
	continue;
      }
      for (let s of t['shift'].split(',')) {
	s = s.trim();
	if (!s) {
	  continue;
	}
	if (!shift_map[s]) {
	  shift_map[s] = [t['name']]
	} else {
	  shift_map[s].push(t['name']);
	}
      }
      let a = (t['area_lead'] || '').trim();
      if (a) {
	if (!area_map[a]) {
	  area_map[a] = [t.name];
	} else {
	  area_map[a].push(t.name);
	}
      }
    }
    console.log(data);
    console.log(shift_map);

    for (let c of data.time_off) {
      if (!c['fields']['Covered By']) {
	coverage_missing.push(c);
      } else {
	coverage_ok.push(c);
      }
    }

    let now = new Date((new Date()).toDateString());
    let end = new Date(now.valueOf());
    end.setDate(end.getDate() + 16);
    let i = 0;
    for (let d = new Date(now.valueOf()); d < end; d.setDate(d.getDate() + 1)) {
      for (let ap of ['AM', 'PM']) {
	let weekday = d.toLocaleDateString('en-US', { weekday: 'long' });
	let s = `${weekday} ${ap}`;
	let people = shift_map[s];
	let id = `Badge${i}`;
	i++;
	let cov_shift_date = `${d.getFullYear()}-${("0"+(d.getMonth()+1)).slice(-2)}-${("0" + d.getDate()).slice(-2)}`;
	for (let cov of data.time_off) {
	  if (cov.fields.Date == cov_shift_date && cov.fields.Shift == ap) {
	    console.log("Coverage match, ", cov);
	    people = people.filter(e => e !== cov.fields['Rendered Shop Tech']);
	    if (cov.fields['Rendered Covered By']) {
	      people.push(`${cov.fields['Rendered Covered By']} (covering ${cov.fields['Rendered Shop Tech']})`);
	    }
	  }
	}
	let color = 'danger';
	if (people.length >= 3) {
	  color = 'success';
	} else if (people.length == 2) {
	  color = 'info';
	} else if (people.length == 1) {
	  color = 'warning';
	}
	let wkd = [
		    'Sun',
		    'Mon',
		    'Tue',
		    'Wed',
		    'Thu',
		    'Fri',
		    'Sat'
		  ][d.getDay()];
	calendar_view.push({title: `${wkd} ${d.getMonth()+1}/${d.getDate()} ${ap}`, color, people, id});
      }
    }
    return data;
  });
}
onMount(refresh);

let show_proposed = true;

function update_tech(t) {
  console.log("Update tech", t);
  post("/techs/update", t).then((rep) => {
      let msg = `${t['name']} updated`;
      toast_msg = {'color': 'success', msg, 'title': 'Edit Success'};
    });
}

function set_enrollment(enroll) {
  enrolling = true;
  post("/techs/enroll", {email: new_tech_email, enroll}).then((data) => {
      console.log(data);
      let msg = `${new_tech_email} successfully ${(enroll) ? 'enrolled' : 'disenrolled'}. Refresh the page to see changes`;
      toast_msg = {'color': 'success', msg, 'title': 'Enrollment changed'};
    }).finally(() => {
      enrolling = false;
    });
}

let modal_open = null;
function clearance_click(id) {
  console.log("clearance_click", id);
  if (modal_open !== id) {
    modal_open = id;
  } else {
    modal_open = null;
  }
}
</script>


{#await promise}
<Spinner/>
{:then p}
<Card style="width: 100%" class="my-3">
  <CardHeader><CardTitle>Tool States</CardTitle></CardHeader>
  <CardBody>
  <Row>
  {#each Object.keys(p.tool_states) as color}
    {#if !color.startsWith('Green') && !color.startsWith('Grey')}
    <Col>
      <Card>
      <CardHeader><CardTitle>{color.split(' ')[0]}</CardTitle></CardHeader>
      <CardBody>
      {#each p.tool_states[color] as tool}
	<div>{tool.name}</div><div>({tool.modified} days)</div>
      {/each}
      </CardBody>
      </Card>
    </Col>
    {/if}
  {/each}
  </Row>
  </CardBody>
</Card>
<Card style="width: 100%" class="my-3">
  <CardHeader>
    <CardTitle>Shift Swaps</CardTitle>
  </CardHeader>
  <CardBody>
  <Row cols={2}>
    <Col>
    <h2>Missing Coverage</h2>
    {#each coverage_missing as s}
      <Card>
	<div>{s.fields['Date']} - {s.fields['Rendered Shop Tech']}</div>
      </Card>
    {/each}
    </Col>
    <Col>
    <h2>Covered Swaps</h2>
    {#each coverage_ok as s}
      <Card>
	<div>{s.fields['Date']} - Shop Tech: {s.fields['Rendered Shop Tech']} covered by {s.fields['Rendered Covered By'] || 'NONE'}</div>
      </Card>
    {/each}
    </Col>
  </Row>
  <h2>Forecast</h2>
  <div class="my-3">
    <p>
    Legend:
    <Badge color='success'>3+ Techs</Badge>
    <Badge color='info'>2 Techs</Badge>
    <Badge color='warning'>1 Tech</Badge>
    <Badge color='danger'>0 Techs</Badge>
    </p>
    <p>Hover over a day for details on shift coverage:</p>
  <div>
  {#each calendar_view as cv}
    <Badge id={cv.id} class="p-2 m-2" color={cv.color}>{cv.title}</Badge>
    <Tooltip target={cv.id} placement="top">
      {#each cv.people as ppl}
	<div>{ppl}</div>
      {/each}
    </Tooltip>
  {/each}
  </div>
  </CardBody>
</Card>
<Card style="width: 100%" class="my-3">
  <CardHeader>
    <CardTitle>Shifts</CardTitle>
  </CardHeader>
  <CardBody>
    <Table class="my-3">
      <thead>
	{#each ['', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'] as d}
	  <th class="mx-3">{d}</th>
	{/each}
      </thead>
      <tbody>
	{#each ['AM', 'PM'] as ap}
	<tr>
	  <td><strong>{ap}</strong></td>
	{#each ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'] as d}
	  <td>
	  {#each shift_map[d + ' ' + ap] || [] as sm}
	    <Card class="my-2 p-2">{sm}</Card>
	  {/each}
	  </td>
	{/each}
	</tr>
	{/each}
      </tbody>
    </Table>
  </CardBody>
</Card>
<Card style="width: 100%" class="my-3">
  <CardHeader><CardTitle>Areas</CardTitle></CardHeader>
  <CardBody>
  <Row>
  {#each p.areas as area}
    <Col class="my-3">
      <Card color={(area_map[area]) ? 'info' : null}>
      <CardHeader><CardTitle>{area}</CardTitle></CardHeader>
      <CardBody>
	{#each area_map[area] || [] as name}
	  <div>{name}</div>
	{/each}
      </CardBody>
      </Card>
    </Col>
  {/each}
  </Row>
  </CardBody>
</Card>
<Card class="my-3" style="width: 100%">
  <CardHeader>
    <CardTitle>Shop Techs</CardTitle>
  </CardHeader>
  <CardBody>
  {#if tech_lead }
  <div class="d-flex">
    {#if enrolling}
      <Spinner/>
    {/if}
    <Input class="mx-1" text bind:value={new_tech_email} disabled={enrolling} placeholder="email address"/>
    <Button class="mx-1" on:click={()=>set_enrollment(true)} disabled={enrolling}>Enroll</Button>
    <Button class="mx-1" on:click={()=>set_enrollment(false)} disabled={enrolling}>Disenroll</Button>
  </div>
  {/if}
  <Toast class="me-1" style="position:fixed; bottom: 2vh; right: 2vh;" autohide isOpen={toast_msg} on:close={() => (toast_msg = null)}>
    <ToastHeader icon={toast_msg.color}>{toast_msg.title}</ToastHeader>
    <ToastBody>{toast_msg.msg}</ToastBody>
  </Toast>

  <Table class="my-3" bordered striped>
    <thead>
      <th class="mx-3">Tech</th>
      <th class="mx-3" style="width:190px;">Shift</th>
      <th class="mx-3" style="min-width:190px">Area Lead</th>
      <th class="mx-3">Interest</th>
      <th class="mx-3">Expertise</th>
      <th id="th-clr" class="mx-3">#Clr</th>
      <Tooltip target="th-clr" placement="top">Number of clearances - click a number for a full list</Tooltip>
    </thead>
    <tbody>
    {#each p.techs as t}
      <tr>
	<td>{t.name} ({t.email})</td>
	<EditCell enabled={tech_lead} on_change={() => update_tech(t)} bind:value={t.shift}/>
	<EditCell enabled={tech_lead} on_change={() => update_tech(t)} bind:value={t.area_lead}/>
	<EditCell enabled={tech_lead} on_change={() => update_tech(t)} bind:value={t.interest}/>
	<EditCell enabled={tech_lead} on_change={() => update_tech(t)} bind:value={t.expertise}/>
	<td><Button outline on:click={() => clearance_click(t.email)}>{t.clearances.length}</Button></td>
      </tr>
      <Modal body header="Clearances" isOpen={modal_open == t.email} toggle={() => clearance_click(t.email)}>
	{#each t.clearances as c}
	  <div>{c}</div>
	{/each}
	{#if tech_lead }
	<div class="my-3">
	  <a href="https://docs.google.com/forms/d/e/1FAIpQLScX3HbZJ1-Fm_XPufidvleu6iLWvMCASZ4rc8rPYcwu_G33gg/viewform" target="_blank">Submit additional clearances</a>
	</div>
	{/if}
      </Modal>
    {/each}
  </Table>
  </CardBody>
</Card>
{:catch error}
	TODO error {error.message}
{/await}
