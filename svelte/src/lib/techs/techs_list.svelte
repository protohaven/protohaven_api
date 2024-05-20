<script type="ts">

import {onMount} from 'svelte';
import { Table, Button, Row, Container, Col, Card, CardHeader, Badge, CardTitle, Modal, CardSubtitle, CardText, Icon, Tooltip, CardFooter, CardBody, Input, Spinner, FormGroup, Navbar, NavbarBrand, Nav, NavItem, Toast, ToastBody, ToastHeader } from '@sveltestrap/sveltestrap';
import {get, post} from '$lib/api.ts';
import EditCell from './editable_td.svelte';

let promise = new Promise((resolve) => {});

let new_tech_email = "";
let toast_msg = null;
let enrolling = false;

function refresh() {
  promise = get("/techs/list");
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
<Card class="my-3" style="width: 100%">
  <CardHeader>
    <CardTitle>Shop Techs</CardTitle>
  </CardHeader>
  <CardBody>
  {#if p.tech_lead }
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

    {#each p.techs as t}
      <Card class="my-2">
	<CardHeader><CardTitle>{t.name} ({t.email})</CardTitle></CardHeader>
	<CardBody>
	<Container>
	<Row cols={{ xxl: 6, xl: 6, l: 6, md: 2, sm: 1, xs: 1}}>
	<EditCell title="Shift" enabled={p.tech_lead} on_change={() => update_tech(t)} bind:value={t.shift}/>
	<EditCell title="Last Day" enabled={p.tech_lead} on_change={() => update_tech(t)} bind:value={t.last_day}/>
	<EditCell title="Area Lead" enabled={p.tech_lead} on_change={() => update_tech(t)} bind:value={t.area_lead}/>
	<EditCell title="Interest" enabled={p.tech_lead} on_change={() => update_tech(t)} bind:value={t.interest}/>
	<EditCell title="Expertise" enabled={p.tech_lead} on_change={() => update_tech(t)} bind:value={t.expertise}/>
	<Col><Button outline on:click={() => clearance_click(t.email)}>{t.clearances.length} Clearance(s)</Button></Col>
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
  </CardBody>
</Card>
{:catch error}
	TODO error {error.message}
{/await}
