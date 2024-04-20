<script type="ts">
  import { Row, Col, Navbar, NavLink, NavItem, NavbarBrand, Button, Icon, Input, Modal, ModalHeader, ModalBody, ModalFooter, Spinner, ListGroup, ListGroupItem, Alert } from '@sveltestrap/sveltestrap';
  import { onMount } from 'svelte';
  export let base_url;
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
    env_promise = fetch(base_url + "/instructor/setup_scheduler_env?" + new URLSearchParams({
      start, end, inst: inst.toLowerCase()})).then((rep) => rep.json()).then((data) => {
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

    solve_promise = fetch(base_url + "/instructor/run_scheduler", {
      headers: {
	'Accept': 'application/json',
	'Content-Type': 'application/json'
      },
      method: "POST",
      body: JSON.stringify(body),
    }).then((rep) => rep.json()).then((data) => {
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
    save_promise = fetch(base_url + "/instructor/push_classes", {
      headers: {
	'Accept': 'application/json',
	'Content-Type': 'application/json'
      },
      method: "POST",
      body: JSON.stringify(body),
    }).then(async (rep) => {
    	let result = await rep.text();
	console.log(result);
    	if (rep.status !== 200) {
	    throw Error(`${rep.status}: ${result}`);
	} else {
	    open = false;
	}
    });
    running = false;
  }
</script>

<Modal size="lg" isOpen={open}>
  <ModalHeader>Class Scheduler</ModalHeader>
  <ModalBody>
    <Navbar expand="md" container="md" ><h5>Instructions</h5></Navbar>

    <p>Use this scheduling prompt to add more classes to your class list!</p>
    <p>The scheduler automatically takes account of other instructors' classes, when they're run, and the areas they run in so scheduling conflicts are avoided.</p>

    <ol>
    	<li>Select the window of time where you want to schedule your classes.</li>
	<li>Make sure your availability is listed on the <a href="https://calendar.google.com/calendar/u/1/r?cid=Y19hYjA0OGUyMTgwNWEwYjVmN2YwOTRhODFmNmRiZDE5YTNjYmE1NTY1YjQwODk2MjU2NTY3OWNkNDhmZmQwMmQ5QGdyb3VwLmNhbGVuZGFyLmdvb2dsZS5jb20" target="_blank">Calendar</a></li>
	<li>Uncheck any classes you don't want the scheduler to add.</li>
	<li>Click on "Run Scheduler" to generate a schedule.</li>
	<li>If you like the generated schedule, click "Save proposed classes" to add them to your class list. Otherwise, edit your settings and re-run the scheduler</li>
    </ol>

    <p>Confirm your availability on each class in the list, then wait for the class scheduler to publish the confirmed classes to our schedule in Neon. You will receive an email when your classes schedule.</p>


    <p><em>Email <a>instructors@protohaven.org</a> if you have any issues.</em></p>

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
