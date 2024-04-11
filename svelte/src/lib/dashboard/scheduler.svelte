<script type="ts">
  import { Row, Col, Navbar, NavLink, NavItem, NavbarBrand, Button, Icon, Input, Modal, ModalHeader, ModalBody, ModalFooter, Spinner, ListGroup, ListGroupItem, Alert } from '@sveltestrap/sveltestrap';
  import { onMount } from 'svelte';
  export let base_url;
  export let email;
  export let open;

  let solve_promise = Promise.resolve([]);

  console.log(email, base_url);


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
  let inst = 'karen kocher'; // TODO actually set the name

  // console.log(start, end);

  let env_promise;
  function reload() {
    console.log("Reloading scheduler env");
    env_promise = fetch(base_url + "/instructor/setup_scheduler_env?" + new URLSearchParams({
      start, end, inst})).then((rep) => rep.json()).then((data) => {
      env = data;

      // Format availability and class info for display
      let avail = data.instructors[0].avail;
      availability = [];
      for (let i = 0; i < avail.length; i+=2) {
	availability.push(`${avail[i]} - ${avail[i+1]}`);
      }
      let cls_ids = new Set(data.instructors[0].caps);
      classes = {};
      for (let cls of data.classes) {
	// console.log(cls.airtable_id, cls.name);
	if (cls_ids.has(cls.airtable_id)) {
	  classes[cls.name] = true;
	}
      }
    });
  }
  reload();

  function run_scheduler() {
    running = true;
    // TODO restrict classes based on selection
    let body = JSON.stringify(env);
    solve_promise = fetch(base_url + "/instructor/run_scheduler", {
      headers: {
	'Accept': 'application/json',
	'Content-Type': 'application/json'
      },
      method: "POST",
      body,
    }).then((rep) => rep.json()).then((data) => {
      output = data[inst];
      for (let cls of output) {
	cls.push(true); // checked
      }
      return output;
    }).finally(()=>running = false);
  }

  function save_schedule() {
    running = true;
    console.error("TODO save schedule");
    running = false;
  }
</script>

<Modal size="lg" isOpen={open}>
  <ModalHeader>Class Scheduler</ModalHeader>
  <ModalBody>
    <em>Use this scheduler to fill your availability with classes! The scheduler automatically takes account
    of other instructors' classes, when they're run, and the areas they run in so scheduling conflicts are avoided.</em>

    <Navbar expand="md" container="md" ><h4>Window</h4></Navbar>
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

    <Navbar expand="md" container="md" ><h4>Availability</h4></Navbar>
    <em>Note: Classes will not be scheduled on weekdays before 5pm, or on US holidays. Be sure to set your availability by visiting the <a>Instructor Availability Calendar</a>. Email <a>instructors@protohaven.org</a> if you have any issues.</em>
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
      Error: {error.message}
    {/await}
    </div>

    <Navbar expand="md" container="md" ><h4>Classes</h4></Navbar>
      <em>Note: classes may not be added to your schedule if your intended date range and availability would cause the class to be scheduled too soon after the previous run of the class. Email <a>instructors@protohaven.org</a> if you think any are missing.</em>

    <div class="my-3">
    {#await env_promise}
      <Spinner/>
    {:then p}
      {#each Object.entries(classes) as [cls, checked]}
	<Input type="checkbox" label={cls} bind:checked={checked}/>
      {/each}
    {:catch error}
      Error: {error.message}
    {/await}
    </div>

    <Navbar expand="md" container="md" >
    <h4>Output</h4>
    </Navbar>

    <div class="my-3">
    {#await solve_promise}
      <Spinner/>
    {:then p}
      {#each p as c}
	<Input type="checkbox" label={`${c[1]} @ ${c[2]}`} bind:checked={c[3]}/>
      {/each}
    {:catch error}
      Error: {error.message}
    {/await}
    </div>

  </ModalBody>
  <ModalFooter>
    <Button on:click={run_scheduler} disabled={running}>Run Scheduler</Button>
    <Button on:click={save_schedule} disabled={running || !output}>Save proposed classes</Button>
    <Button on:click={() => open = false}>Close</Button>
  </ModalFooter>
</Modal>

<style>
  h4 {
    margin-top: 20px;
  }
</style>
