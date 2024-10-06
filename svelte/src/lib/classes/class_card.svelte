<script type="typescript">
import { onMount } from 'svelte';
import { Button, Row, Modal, ModalHeader, ModalFooter, ModalBody, Col, Card, CardHeader, CardTitle, CardSubtitle, Image, CardText, CardFooter, CardBody, Icon, Spinner, FormGroup, ListGroup, ListGroupItem, Navbar, NavbarBrand, Nav, NavItem, Alert } from '@sveltestrap/sveltestrap';

export let c;


function open_signup(id) {
  let url = "https://protohaven.app.neoncrm.com/np/clients/protohaven/eventRegistration.jsp?event="+c['id'];
  window.open(url, "_blank");
}

let img_src = "https://api.protohaven.org/static/img/favicon.jpg";
let img_thumb = "https://api.protohaven.org/static/img/favicon.jpg";
let data = {};
$: {
  let img_data = (c['airtable_data'] || {'fields': {}})['fields']['Image (from Class)'];
  if (img_data && img_data.length) {
  	console.log(img_data);
	img_src = img_data[0]['url'];
	if (img_data[0].thumbnails) {
		img_thumb = img_data[0]['thumbnails']['large']['url'];
	} else {
		img_thumb = img_src;
	}
  }

  if (c['airtable_data']) {
    let f = c['airtable_data']['fields'];

    let dates = [];
    let startDate = new Date(c['timestamp']);
    for (let i = 0; i < f['Days (from Class)']; i++) {
      let d = new Date(startDate);
      d.setDate(startDate.getDate() + 7*i);
      dates.push(d.toLocaleDateString());
    }

    data = {
      price: f['Price (from Class)'],
      hours: f['Hours (from Class)'],
      age: f['Age Requirement (from Class)'],
      description: f['Short Description (from Class)'],
      what_bring_wear: f['What to Bring/Wear (from Class)'],
      what_create: f['What you Will Create (from Class)'],
      instructor: f['Instructor'],
      dates,
    };
  }
}

let open = false;
const toggle = () => (open = !open);
</script>
<Card on:click={toggle} class="my-3" style="cursor:pointer">
{#if img_thumb}
      <Image fluid src={img_thumb} alt="class image"/>
{/if}
<CardHeader><CardTitle>{c['name']}></CardTitle></CardHeader>
<CardBody>
<ListGroup>
  <ListGroupItem><Icon name="calendar" /> {c['day']}</ListGroupItem>
  <ListGroupItem><Icon name="clock" /> {c['time']}</ListGroupItem>
  {#if data.hours}
  <ListGroupItem><Icon name="hourglass" /> {data.hours}-Hour Workshop</ListGroupItem>
  {/if}
  {#if data.age}
  <ListGroupItem><Icon name="speedometer2" /> Ages {data.age}</ListGroupItem>
  {/if}
</ListGroup>
</CardBody>
{#if data.price}
<CardFooter>
${data.price} (members: $TODO)
</CardFooter>
{/if}
</Card>

<Modal isOpen={open} {toggle} size="xl">
<ModalHeader {toggle}>{c['name']}</ModalHeader>
<ModalBody>
{#if !c['airtable_data']}
  {@html c['description']}
{:else}
  <Image fluid src={img_src} alt="class image"/>
  <p>{data.description}</p>
  <ListGroup>
  <ListGroupItem>What you will create: {data.what_create}</ListGroupItem>
  <ListGroupItem>What to Bring / Wear: {data.what_bring_wear}</ListGroupItem>
  <ListGroupItem>Age Requirement: {data.age}</ListGroupItem>
  <ListGroupItem>Class Dates: {data.dates}</ListGroupItem>
  <ListGroupItem>Instructor: {data.instructor}</ListGroupItem>
  </ListGroup>
{/if}
</ModalBody>
<ModalFooter>
  <Button color="primary" on:click={open_signup}>Register</Button>
  <Button color="secondary" on:click={toggle}>Close</Button>
</ModalFooter>
</Modal>
