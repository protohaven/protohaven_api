<script type="ts">
  import { Row, Col, Navbar, NavLink, NavItem, NavbarBrand, Button, Icon, Input, Modal, ModalHeader, ModalBody, ModalFooter, Spinner, ListGroup, ListGroupItem, Alert } from '@sveltestrap/sveltestrap';
  import { onMount } from 'svelte';
  import {get, post} from '$lib/api.ts';
  export let email;
  export let open;
  export let inst;

  let solve_promise = Promise.resolve([]);
  let save_promise = Promise.resolve(null);

  let classes = {};
  let availability = [];

  let start = new Date();
  start.setDate(start.getDate() + 14);
  start = start.toJSON().slice(0, 10);
  let end = new Date();
  end.setDate(end.getDate() + 40);
  end = end.toJSON().slice(0,10);
  let running = false;
  let env = null;
  let output = null;

  // console.log(start, end);

  let env_promise;
  function reload() {
    console.log("Reloading scheduler env");
    env_promise = get("/instructor/setup_scheduler_env?" + new URLSearchParams({
      start, end, inst: inst.toLowerCase()})).then((data) => {
      env = data;

      // Format availability and class info for display
      let avail = data.instructors[0].avail;
      availability = [];
      for (let i = 0; i < avail.length; i++) {
	availability.push(`${(new Date(avail[i])).toLocaleString()}`);
      }
      let cls_ids = new Set(data.instructors[0].caps);
      classes = {};
      for (let cls of data.classes) {
	// console.log(cls.airtable_id, cls.name);
	if (cls_ids.has(cls.airtable_id)) {
	  classes[cls.airtable_id] = {name: cls.name, checked: true};
	}
      }
    });
  }
  $: {
    if (open) {
    	reload();
    }
  }

  function run_scheduler() {
    running = true;
    // Clone environment so we can strip deselected classes
    // without affecting the actual env
    let body = JSON.parse(JSON.stringify(env));
    body.instructors[0].caps = [];
    for (let cap of env.instructors[0].caps) {
      if (classes[cap].checked) {
	body.instructors[0].caps.push(cap);
      }
    }
    console.log(body.instructors[0].caps);

    solve_promise = post("/instructor/run_scheduler", body).then((data) => {
      output = data[inst.toLowerCase()];
      for (let cls of output) {
      	console.log(cls);
	cls[2] = (new Date(cls[2])).toLocaleString();
	cls.push(true); // checked
      }
      return output;
    }).finally(()=>running = false);
  }

  function save_schedule() {
    running = true;
    let body = [];
    for (let cls of output) {
    	if (cls[3]) {
		body.push([cls[0], cls[1], cls[2]]);
	}
    }
    let data = {};
    data[inst] = body;
    save_promise = post("/instructor/push_classes", data).then((rep) => open = false);
    running = false;
  }
</script>

<Modal size="lg" isOpen={open}>
  <ModalHeader>Class Scheduler</ModalHeader>
  <ModalBody>
    <Navbar expand="md" container="md" ><h5>Instructions</h5></Navbar>

    <p>Use this scheduling prompt to add more classes to your class list!</p>

    <ol>
    	<li>Select the window of time where you want to schedule your classes, or use the default.</li>
	<li>Make sure your availability is listed on the <a href="https://calendar.google.com/calendar/u/1/r?cid=Y19hYjA0OGUyMTgwNWEwYjVmN2YwOTRhODFmNmRiZDE5YTNjYmE1NTY1YjQwODk2MjU2NTY3OWNkNDhmZmQwMmQ5QGdyb3VwLmNhbGVuZGFyLmdvb2dsZS5jb20" target="_blank">Availability Calendar</a>.</li>
	<li>Under Classes, uncheck any classes you don't want the scheduler to add.</li>
	<li>Click on "Run Scheduler" to generate a schedule.</li>
	<li>If you like the generated schedule, click "Save proposed classes" to add them to your class list. Otherwise, edit your settings and re-run the scheduler</li>
	<li>Confirm your availability on each class in the list, then wait for the class scheduler to publish the confirmed classes to our schedule in Neon.</li>
    </ol>

    <p>You will receive an email when your classes schedule. Email <a href="mailto:instructors@protohaven.org">instructors@protohaven.org</a> if you have any issues.</p>

    <Navbar expand="md" container="md" ><h5>Behavior</h5></Navbar>

    <p>No classes are scheduled:</p>

    <ul>
      <li>on US holidays</li>
      <li>before 5pm on a weekday</li>
      <li>concurrently in the same area (e.g. never two textiles classes)</li>
      <li>when an instructor is already teaching a class</li>
      <li>to an instructor that cannot teach them.</li>
      <li>at a time the instructor has not listed as available</li>
      <li>too soon after the previous run of the class (usually, a month)</li>
    </ul>

    <p>The scheduler will propose classes that overlap with other unpublished classes. When the automation runs to publish classes, it will publish whichever class was confirmed earliest.</p>

    <p><em>Email <a href="mailto:instructors@protohaven.org">instructors@protohaven.org</a> or reach out on the #instructors channel if you suspect any of these rules are not being observed.</p>

    <Navbar expand="md" container="md" ><h5>Window</h5></Navbar>
    <p>This is the start and end date between which classes will be generated. It defaults to 14-40 days away from the current date.</p>
    <Row cols={2}>
    <Col>
    From
    <Input type="date" placeholder="From Date" value={start} on:change={reload}/>
    </Col>
    <Col>
    Until
    <Input type="date" placeholder="Until Date" value={end} on:change={reload}/>
    </Col>
    </Row>

    <Navbar expand="md" container="md" ><h5>Availability</h5></Navbar>
    <p>Classes will be generated at the following times, based on your availability in the <a href="https://calendar.google.com/calendar/u/1/r?cid=Y19hYjA0OGUyMTgwNWEwYjVmN2YwOTRhODFmNmRiZDE5YTNjYmE1NTY1YjQwODk2MjU2NTY3OWNkNDhmZmQwMmQ5QGdyb3VwLmNhbGVuZGFyLmdvb2dsZS5jb20" target="_blank">Instructor Availability Calendar</a>.</p>
    <p><em>Note: Classes will not be scheduled on weekdays before 5pm, or on US holidays.</em></p>
    <div class="my-3">
    {#await env_promise}
      <Spinner/>
    {:then p}
      <ListGroup>
      {#each availability as a}
	<ListGroupItem>{a}</ListGroupItem>
      {/each}
      </ListGroup>
    {:catch error}
      <Alert color="danger">{error.message}</Alert>
    {/await}
    </div>

    <Navbar expand="md" container="md" ><h5>Classes</h5></Navbar>
      <p>This list includes all the classes you are registered to teach. Deselect any classes you do not wish to be generated.</p>
      <p><em>Note: classes may not be added to your schedule if your intended date range and availability would cause the class to be scheduled too soon after the previous run of the class.</em></p>

    <div class="my-3">
    {#await env_promise}
      <Spinner/>
    {:then p}
      {#each Object.values(classes) as cls}
	<Input type="checkbox" label={cls.name} bind:checked={cls.checked}/>
      {/each}
    {:catch error}
      <Alert color="danger">{error.message}</Alert>
    {/await}
    </div>

    <Navbar expand="md" container="md" >
    <h5>Output</h5>
    </Navbar>

    <div class="my-3">
    {#await solve_promise}
      <Spinner/>
    {:then p}
      {#each p as c}
	<Input type="checkbox" label={`${c[2]}: ${c[1]}`} bind:checked={c[3]}/>
      {/each}
    {:catch error}
      <Alert color="danger">{error.message}</Alert>
    {/await}
    </div>

    {#await save_promise}
    	<Spinner/>
    {:catch error}
      <Alert color="danger">{error.message}</Alert>
    {/await}
  </ModalBody>
  <ModalFooter>
    <Button on:click={run_scheduler} disabled={running}>Run Scheduler</Button>
    <Button on:click={save_schedule} disabled={running || !output}>Save proposed classes</Button>
    <Button on:click={() => open = false}>Close</Button>
  </ModalFooter>
</Modal>

<style>
  h5 {
    margin-top: 20px;
  }
</style>
