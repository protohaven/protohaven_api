<script type="typescript">
  import { Row, Col, Button, Badge, Icon, Input, Modal, ModalHeader, ModalBody, ModalFooter, Spinner, ListGroup, Accordion, AccordionItem, ListGroupItem, Alert } from '@sveltestrap/sveltestrap';
  import { onMount } from 'svelte';
  import Calendar from '$lib/dashboard/calendar.svelte';
  import {get, post, isodate} from '$lib/api.ts';
  export let open;
  export let inst;
  export let inst_id;

  let solve_promise = Promise.resolve([]);
  let save_promise = Promise.resolve(null);

  let classes = {};
  let candidates = {};
  let rejected = {};

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
  const MAX_DATE_RANGE = 60;
  function reload(src) {
    // Make sure date range is reasonable
    if (end <= start || (new Date(end).getTime() - new Date(start).getTime()) / (24*60*60*1000) > MAX_DATE_RANGE) {
    	console.log("Date crunch; moving the one other than " + src, start, end);
      if (src === "end") {
        start = new Date(end);
        start.setDate(start.getDate() - MAX_DATE_RANGE);
        start = isodate(start);
      } else {
        end = new Date(start);
        end.setDate(end.getDate() + MAX_DATE_RANGE);
        end = isodate(end);
      }
      console.log("Now", start, end);
    }

    console.log("Reloading scheduler env");
    env_promise = get("/instructor/setup_scheduler_env?" + new URLSearchParams({
      start, end, inst: inst.toLowerCase()})).then((data) => {
      env = data;

      if (data.instructors.length === 0) {
        throw Error(`No instructor data found for interval ${start} to ${end}.\n\nThe scheduler currently picks only times >2wks from now where you are fully available from 6-9pm weeknights, or weekends from 10am-1pm, 1pm-4pm, 2pm-5pm, or 6pm-9pm.\n\nPlease check the calendar to ensure you have availability in that range.`);
      }

      // Format candidates, rejected and class info for display
      candidates = data.instructors[0].candidates;
      rejected = data.instructors[0].rejected;

      let cls_ids = new Set(Object.keys(candidates) || []);
      classes = {};
      for (let cls of data.classes) {
        if (cls_ids.has(cls.class_id)) {
          classes[cls.class_id] = {name: cls.name, checked: true};
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
    body.instructors[0].candidates = {};
    for (let cap of Object.keys(env.instructors[0].candidates)) {
      if (classes[cap] && classes[cap].checked) {
	      body.instructors[0].candidates[cap] = env.instructors[0].candidates[cap];
      }
    }
    console.log(body.instructors[0].candidates);

    solve_promise = post("/instructor/run_scheduler", body).then((data) => {
      console.log(data);
      output = data.result[inst.toLowerCase()];
      if (!output) {
        console.log("No result for instructor - output", output);
	throw Error("The scheduler ran but no schedule was able to be generated.");
      }
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
    <Input type="date" placeholder="From Date" bind:value={start} on:change={() => reload("start")}/>
    </Col>
    <Col>
    Until
    <Input type="date" placeholder="Until Date" bind:value={end} on:change={() => reload("end")}/>
    </Col>
    </Row>


    <Calendar {inst} {inst_id} {start} {end} date_edited={() => {console.log('ONCHANGE'); reload("start")}}></Calendar>

    <h5>2. Check Availability</h5>
    <p>Edit your availability in the calendar above, then check here to see what the scheduler is able to use.</p>
    {#await env_promise}
      <Spinner/>
    {:then p}
	      <div class="my-3">
        {#if Object.keys(candidates).length == 0}
          <Alert color="warning"><strong>No good times found for scheduling classes. Click <a href="https://protohaven.org/wiki/instructors#scheduling" target="_blank">HERE</a> for more info on how the scheduler picks times.</strong></Alert>
        {/if}

	      {#each Object.keys(candidates) as k}
        <div class="mt-3">{(classes[k] || "").name}</div>
	      <div>
          {#if candidates[k].length == 0}
            <em>No good times found for scheduling this class</em>
          {/if}
          {#each candidates[k] as c}
		      <Badge color="light">{(new Date(c)).toLocaleString()}</Badge>
          {/each}
	      </div>
	      {/each}

        {#if Object.keys(rejected).length > 0}
	      <Accordion id="rejected_flyout" class="my-3" stayOpen>
	      	<AccordionItem header="Scheduler passed on some of your available windows - click for details">
          {#each Object.keys(rejected) as k}
          <div>{(classes[k] || "").name || k}</div>
          <ListGroup>
            {#each rejected[k] as r}
            <ListGroupItem>Skip {(new Date(r.time)).toLocaleString()}: {r.reason}</ListGroupItem>
            {/each}
          </ListGroup>
          {/each}

          <div class="my-3">
            See <strong><a href="https://protohaven.org/wiki/instructors#scheduling" target="_blank">the Instructor wiki page</a></strong> for more details.
          </div>
          </AccordionItem>
        </Accordion>
        {/if}
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
  :global(#rejected_flyout button) {
    background-color: var(--bs-warning) !important;
  }

</style>
