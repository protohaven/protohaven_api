<script type="ts">
  import { Row, Col, Button, Icon, Input, Modal, ModalHeader, ModalBody, ModalFooter, Spinner, ListGroup, Accordion, AccordionItem, ListGroupItem, Alert } from '@sveltestrap/sveltestrap';
  import { onMount } from 'svelte';
  import Calendar from '$lib/dashboard/calendar.svelte';
  import {get, post, isodate} from '$lib/api.ts';
  export let email;
  export let open;
  export let inst;
  export let inst_id;

  let solve_promise = Promise.resolve([]);
  let save_promise = Promise.resolve(null);

  let classes = {};
  let availability = [];

  let start = new Date();
  start.setDate(start.getDate() + 14);
  start = isodate(start);
  let end = new Date();
  end.setDate(end.getDate() + 40);
  end = isodate(end); 
  let running = false;
  let env = null;
  let output = null;
  let run_details = null;

  // console.log(start, end);

  let env_promise;
  function reload() {
    console.log("Reloading scheduler env");
    env_promise = get("/instructor/setup_scheduler_env?" + new URLSearchParams({
      start, end, inst: inst.toLowerCase()})).then((data) => {
      env = data;

      if (data.instructors.length === 0) {
        throw Error(`No instructor data found for interval ${start} to ${end}.\n\nThe scheduler currently picks only times >2wks from now where you are fully available from 6-9pm weeknights, or weekends from 10am-1pm, 1pm-4pm, 2pm-5pm, or 6pm-9pm.\n\nPlease check the calendar to ensure you have availability in that range.`);
      }

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
      console.log(data);
      output = data.result[inst.toLowerCase()];
      run_details = data.skip_counters[inst.toLowerCase()];
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
    <strong>See <a href="https://protohaven.org/wiki/instructors#scheduling" target="_blank">the Instructor wiki page</a> for details and a video tutorial on how to use this scheduler.</strong>

    <h5>1. Pick Scheduling Window</h5>
    <p>Select the window of time where you want to schedule your classes, and build your availability.</p>
    <Row cols={2}>
    <Col>
    From
    <Input type="date" placeholder="From Date" bind:value={start} on:change={reload}/>
    </Col>
    <Col>
    Until
    <Input type="date" placeholder="Until Date" bind:value={end} on:change={reload}/>
    </Col>
    </Row>

    
    <Calendar {inst} {inst_id} {start} {end}></Calendar>

    <h5>2. Check Availability</h5>
    <p>Edit your availability in the <a href="https://calendar.google.com/calendar/u/1/r?cid=Y19hYjA0OGUyMTgwNWEwYjVmN2YwOTRhODFmNmRiZDE5YTNjYmE1NTY1YjQwODk2MjU2NTY3OWNkNDhmZmQwMmQ5QGdyb3VwLmNhbGVuZGFyLmdvb2dsZS5jb20" target="_blank">Instructor Availability Calendar</a>. if you wish to change any of the generated schedule times here.</p>
    {#await env_promise}
      <Spinner/>
    {:then p}
	      <div class="my-3">
	      <ListGroup>
	      {#each availability as a}
		<ListGroupItem>{a}</ListGroupItem>
	      {/each}
	      </ListGroup>
	      </div>

	      <h5>3. Select Classes to Include</h5>
	      <p>Deselect any classes you do not wish to schedule.</p>
	      <div class="my-3">
	      {#each Object.values(classes) as cls}
		<Input type="checkbox" label={cls.name} bind:checked={cls.checked}/>
	      {/each}
	      </div>

	    <h5>4. Generate New Proposed Classes</h5>
	    <Button on:click={run_scheduler} disabled={running}>Run Scheduler</Button>

	    <div class="my-3">
	    {#await solve_promise}
	      <Spinner/>
	    {:then p}
	      {#each p as c}
		<Input type="checkbox" label={`${c[2]}: ${c[1]}`} bind:checked={c[3]}/>
	      {/each}

	      {#if run_details}
	      <Accordion class="my-3" stayOpen>
	      	<AccordionItem header="Some dates were excluded from scheduling particular classes - click for details">
	        {#each Object.keys(run_details) as d}
		  <strong>{d}:</strong>
	      	<ul>
		  {#each run_details[d] as skip_info}
		     <li>{isodate(skip_info[0])} (confict with {skip_info[2]} on {isodate(skip_info[1])})</li>
		  {/each}
		</ul>
		{/each}
		</AccordionItem>
	      </Accordion>
	      {/if}

	      {#if output}
		<Alert color="warning"><strong>Your classes aren't saved yet!</strong> Click "save proposed classes" below to add them to your schedule.</Alert>
	      {/if}
	    {:catch error}
	      <Alert color="danger">{error.message.replace("Invalid reply from server: ", "")}</Alert>
	    {/await}
	    </div>

    {:catch error}
      <Alert color="danger">{error.message}</Alert>
    {/await}

    {#await save_promise}
    	<Spinner/>
    {:catch error}
      <Alert color="danger">{error.message}</Alert>
    {/await}
  </ModalBody>
  <ModalFooter>
    <Button on:click={save_schedule} disabled={running || !output}>Save proposed classes</Button>
    <Button on:click={() => open = false}>Close</Button>
  </ModalFooter>
</Modal>

<style>
  h5 {
    margin-top: 20px;
  }
</style>
