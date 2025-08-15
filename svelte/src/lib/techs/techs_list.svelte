<script type="typescript">

import {onMount} from 'svelte';
import { Table, Dropdown, DropdownToggle, DropdownItem, DropdownMenu, Button, Row, Container, Col, Card, CardHeader, Badge, CardTitle, Modal, CardSubtitle, CardText, Icon, Tooltip, CardFooter, CardBody, Input, Spinner, FormGroup, Navbar, NavbarBrand, Nav, NavItem, Toast, ToastBody, ToastHeader } from '@sveltestrap/sveltestrap';
import {get, post} from '$lib/api.ts';
import FetchError from '../fetch_error.svelte';

import EditCell from './editable_td.svelte';

export let visible;
let loaded = false;
let promise = new Promise((resolve) => {});

let new_tech_email = "";
let toast_msg = null;
let enrolling = false;

let techs = [];
let techs_sorted = []
let sort_type = "clearances_desc";
$: {
  if (sort_type === "clearances_desc") {
    techs_sorted = [...techs].sort((a, b) => b.clearances.length - a.clearances.length);
  } else if (sort_type === "clearances_asc") {
    techs_sorted = [...techs].sort((a, b) => a.clearances.length - b.clearances.length);
  } else if (sort_type === "name") {
    techs_sorted = [...techs].sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()));
  }
}
function refresh() {
  promise = get("/techs/list").then((data) => {
    loaded = true;
    techs = data.techs.map((t) => {
      return {...t, shop_tech_shift: t.shop_tech_shift.join(' ')};
    });
    return data;
  });
}
$: {
  if (visible && !loaded) {
    refresh();
  }
}

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

{#if visible}
<Card>
    <CardHeader>
      <CardTitle>Tech Roster</CardTitle>
      <CardSubtitle>Current info on all techs</CardSubtitle>
    </CardHeader>
<CardBody>
{#await promise}
<Spinner/>
{:then p}
  <div class="d-flex">
    {#if enrolling}
      <Spinner/>
    {/if}
    <Dropdown>
        <DropdownToggle color="light" caret>
            Sort
        </DropdownToggle>
        <DropdownMenu>
            <DropdownItem on:click={() => sort_type="clearances_asc" }>Least Clearances</DropdownItem>
            <DropdownItem on:click={() => sort_type="clearances_desc" }>Most Clearances</DropdownItem>
            <DropdownItem on:click={() => sort_type="name" }>By Name</DropdownItem>
        </DropdownMenu>
    </Dropdown>
    {#if p.tech_lead }
      <Input class="mx-1" text bind:value={new_tech_email} disabled={enrolling} placeholder="email address"/>
      <Button class="mx-1" on:click={()=>set_enrollment(true)} disabled={enrolling}>Enroll</Button>
      <Button class="mx-1" on:click={()=>set_enrollment(false)} disabled={enrolling}>Disenroll</Button>
    {/if}
  </div>
  <Toast class="me-1" style="position:fixed; bottom: 2vh; right: 2vh;" autohide isOpen={toast_msg} on:close={() => (toast_msg = null)}>
    <ToastHeader icon={toast_msg.color}>{toast_msg.title}</ToastHeader>
    <ToastBody>{toast_msg.msg}</ToastBody>
  </Toast>

    {#each techs_sorted as t}
      <Card class="my-2">
	<CardHeader><CardTitle>{t.name} ({t.email})</CardTitle></CardHeader>
	<CardBody>
	<Container style="max-width: none;">
	<Row cols={{ xxl: 2, xl: 2, l: 2, md: 2, sm: 1, xs: 1}}>
    <Col>
      <Row cols={{ xxl: 2, xl: 2, l: 2, md: 1, sm: 1, xs: 1}}>
      {#if t.volunteer_bio}
        <img src={t.volunteer_picture} style="max-width: 200px;">
        <div>
          <strong>Bio</strong>
        <div>{t.volunteer_bio}</div>
        </div>
      {/if}
      </Row>
    </Col>
    <Col>
      <EditCell title="Shift" enabled={p.tech_lead} on_change={() => update_tech(t)} bind:value={t.shop_tech_shift}/>
      <EditCell title="First Day" enabled={p.tech_lead} on_change={() => update_tech(t)} bind:value={t.shop_tech_first_day}/>
      <EditCell title="Last Day" enabled={p.tech_lead} on_change={() => update_tech(t)} bind:value={t.shop_tech_last_day}/>
      <EditCell title="Area Lead" enabled={p.tech_lead} on_change={() => update_tech(t)} bind:value={t.area_lead}/>
      <EditCell title="Interest" enabled={p.tech_lead} on_change={() => update_tech(t)} bind:value={t.interest}/>
      <EditCell title="Expertise" enabled={p.tech_lead} on_change={() => update_tech(t)} bind:value={t.expertise}/>
      <Col><Button outline on:click={() => clearance_click(t.email)}>{t.clearances.length} Clearance(s)</Button></Col>
    </Col>
	</Row>
	</Container>
	</CardBody>
      </Card>
      <Modal body header="Clearances" isOpen={modal_open == t.email} toggle={() => clearance_click(t.email)}>
	{#each t.clearances as c}
	  <div>{c}</div>
	{/each}
	{#if p.tech_lead }
	<div class="my-3">
	  <a href="https://docs.google.com/forms/d/e/1FAIpQLScX3HbZJ1-Fm_XPufidvleu6iLWvMCASZ4rc8rPYcwu_G33gg/viewform" target="_blank">Submit additional clearances</a>
	</div>
	{/if}
      </Modal>
    {/each}
{:catch error}
  <FetchError {error}/>
{/await}
</CardBody>
</Card>
{/if}
