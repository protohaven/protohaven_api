<script type="typescript">

import {onMount} from 'svelte';
import { Table, Dropdown, DropdownToggle, DropdownItem, DropdownMenu, Button, Row, Container, Col, Card, CardHeader, Badge, CardTitle, Modal, CardSubtitle, CardText, Icon, Tooltip, CardFooter, CardBody, Input, Spinner, FormGroup, Navbar, NavbarBrand, Nav, NavItem, Toast, ToastBody, ToastHeader } from '@sveltestrap/sveltestrap';
import {get, post} from '$lib/api.ts';
import FetchError from '../fetch_error.svelte';

import EditCell from './editable_td.svelte';

export let visible;
export let user;
let loaded = false;
let promise = new Promise((resolve) => {});

let new_tech = {neon_id: null, name: "", email:""};
let toast_msg = null;
let potential_volunteers = [];
let show_create_account = false;
let enrolling = false;

let techs = [];
let techs_sorted = []
let user_data = null;
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
      if (t.email.trim().toLowerCase() === user.email.trim().toLowerCase()) {
        user_data = t;
      }
      return {...t, shop_tech_shift: t.shop_tech_shift.join(' ')};
    });

    // Fetch potential volunteers if user is a tech lead
    if (data.tech_lead) {
      get("/techs/volunteers").then((data) => {
        potential_volunteers = data.volunteers;
      }).catch((err) => {
        console.error("Failed to fetch volunteers:", err);
      });
    }

    return data;
  });
}
$: {
  if (visible && !loaded) {
    refresh();
  }
}

let show_proposed = true;

function is_enrolled(neon_id) {
  console.log("is_enrolled", neon_id);
  for (let t of techs || []) {
    if (t.neon_id == neon_id) {
      return true;
    }
  }
  return false;
}

function update_tech(t) {
  console.log("Update tech", t);
  post("/techs/update", t).then((rep) => {
      let msg = `${t['name']} updated`;
      toast_msg = {'color': 'success', msg, 'title': 'Edit Success'};
    });
}

function set_enrollment(enroll) {
  enrolling = true;

  let payload = {
    ...new_tech,
    enroll
  };

  // If we're creating a new account, include name and email
  if (show_create_account && enroll) {
    payload['create_account'] = true;
  }

  post("/techs/enroll", payload).then((data) => {
      console.log(data);
      let msg = `${payload.name} successfully ${(enroll) ? 'enrolled' : 'disenrolled'}.`;
      toast_msg = {'color': 'success', msg, 'title': 'Enrollment changed'};

      // Reset form
      if (show_create_account) {
        show_create_account = false;
        new_tech.name = "";
        new_tech.email = "";
      }
      new_tech.neon_id = null;

      // Refresh the list
      refresh();
    }).catch((err) => {
      console.error(err);
      toast_msg = {'color': 'danger', 'msg': 'See console for details', 'title': 'Error Changing Enrollment'};
    }).finally(() => {
      enrolling = false;
    });
}

function disenroll_tech(t) {
  if (!confirm(`Are you sure you want to disenroll ${t.name} as a shop tech?`)) {
    console.log("Cancelled disenrollment");
    return;
  }
  enrolling = true;
  post("/techs/enroll", {neon_id: t.neon_id, enroll: false}).then((data) => {
      console.log("Enrollment result", data);
      let msg = `${t.name} successfully disenrolled. Refresh the page to see changes`;
      toast_msg = {'color': 'success', msg, 'title': 'Disenrollment successful'};
      // Refresh the list after a short delay
      setTimeout(() => refresh(), 1000);
    }).catch((err) => {
      console.error(err);
      toast_msg = {'color': 'danger', 'msg': 'See console for details', 'title': 'Error Disenrolling'};
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
  {#if user_data }
    <Card class="my-2">
    <CardHeader><CardTitle>{user_data.name} ({user_data.email})</CardTitle></CardHeader>
    <CardBody>
      <Container style="max-width: none;">
      <Row cols={{ xxl: 2, xl: 2, l: 2, md: 2, sm: 1, xs: 1}}>
        <Col>
          <Row cols={{ xxl: 2, xl: 2, l: 2, md: 1, sm: 1, xs: 1}}>
          {#if user_data.volunteer_bio}
            <img src={user_data.volunteer_picture} style="max-width: 200px;">
            <div>
              <strong>Bio</strong>
            <div>{user_data.volunteer_bio}</div>
            </div>
          {:else}
            <a href="https://protohaven.org/mugshot" target="_blank">Submit your photo and bio!</a>
          {/if}
          </Row>
        </Col>
        <Col>
          <EditCell title="Shift" enabled={p.tech_lead} on_change={() => update_tech(user_data)} bind:value={user_data.shop_tech_shift}/>
          <EditCell title="First Day" enabled={p.tech_lead} on_change={() => update_tech(user_data)} bind:value={user_data.shop_tech_first_day}/>
          <EditCell title="Last Day" enabled={p.tech_lead} on_change={() => update_tech(user_data)} bind:value={user_data.shop_tech_last_day}/>
          <EditCell title="Area Lead" enabled={p.tech_lead} on_change={() => update_tech(user_data)} bind:value={user_data.area_lead}/>
          <EditCell title="Interest" enabled={true} on_change={() => update_tech(user_data)} bind:value={user_data.interest}/>
          <EditCell title="Expertise" enabled={true} on_change={() => update_tech(user_data)} bind:value={user_data.expertise}/>
          <Col><Button outline on:click={() => clearance_click(user_data.email)}>{user_data.clearances.length} Clearance(s)</Button></Col>
        </Col>
      </Row>
      </Container>
    </CardBody>
    </Card>
    <hr>
  {/if}

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
      {#if !show_create_account}
        <Dropdown class="mx-1">
          <DropdownToggle color="light" caret disabled={enrolling}>
            {#if new_tech.name || new_tech.email}
              {new_tech.name} ({new_tech.email})
            {:else}
              Select volunteer...
            {/if}
          </DropdownToggle>
          <DropdownMenu>
            {#each potential_volunteers as volunteer}
              <DropdownItem on:click={() => {
                new_tech = {neon_id: volunteer.neon_id, name: volunteer.name, email: volunteer.email};
                show_create_account = false;
              }}>
                {volunteer.name} ({volunteer.email})
                {#if volunteer.roles.length > 0}
                  <Badge color="info" pill class="ms-1">{volunteer.roles.length} role(s)</Badge>
                {/if}
              </DropdownItem>
            {/each}
            <DropdownItem divider />
            <DropdownItem on:click={() => {
              new_tech.neon_id = null;
              new_tech.email = "";
              show_create_account = true;
            }}>
              <Icon name="plus" class="me-1" /> Create new Neon account
            </DropdownItem>
          </DropdownMenu>
        </Dropdown>
      {:else}
        <div class="mx-1 d-flex align-items-center">
          <Input class="me-1" text bind:value={new_tech.name} placeholder="Full name" disabled={enrolling} />
          <Input class="me-1" text bind:value={new_tech.email} placeholder="Email address" disabled={enrolling} />
          <Button color="secondary" size="sm" on:click={() => {
            show_create_account = false;
            new_tech.name = "";
            new_tech.email = "";
          }} disabled={enrolling}>
            Cancel
          </Button>
        </div>
      {/if}

      <Button class="mx-1" on:click={()=>set_enrollment(true)} disabled={enrolling || is_enrolled(new_tech.neon_id) || !new_tech.name || !new_tech.email}>
        {#if show_create_account}
          Create & Enroll
        {:else}
          Enroll
        {/if}
      </Button>
      <Button class="mx-1" on:click={()=>set_enrollment(false)} disabled={enrolling || (new_tech.neon_id && !is_enrolled(new_tech.neon_id)) || !new_tech.neon_id}>Disenroll</Button>
    {/if}
  </div>
  <Toast class="me-1" style="z-index: 10000; position:fixed; bottom: 2vh; right: 2vh;" autohide isOpen={toast_msg} on:close={() => (toast_msg = null)}>
    <ToastHeader icon={toast_msg.color}>{toast_msg.title}</ToastHeader>
    <ToastBody>{toast_msg.msg}</ToastBody>
  </Toast>
  {#each techs_sorted as t}
    <Card class="my-2">
	<CardHeader>
	  <div class="d-flex justify-content-between align-items-center">
	    <CardTitle>{t.name} ({t.email})</CardTitle>
	    {#if p.tech_lead}
	      <Button color="danger" size="sm" on:click={() => disenroll_tech(t)} title="Disenroll {t.name}">Disenroll</Button>
	    {/if}
	  </div>
	</CardHeader>
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
