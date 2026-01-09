<script type="typescript">
  import { Dropdown, DropdownMenu, DropdownItem, DropdownToggle, Row, Col, Button, Badge, Icon, Input, Modal, ModalHeader, ModalBody, ModalFooter, Spinner, ListGroup, Accordion, AccordionItem, ListGroupItem, Alert } from '@sveltestrap/sveltestrap';
  import { onMount } from 'svelte';
  import {get, post, isodatetime} from '$lib/api.ts';
  export let open;
  export let inst;
  export let inst_id;
  export let templates = {};
  export let classes = {};
  export let admin;
  export let email;

  let ovr = false;
  let validation_override = "";
  $: ovr = (validation_override.replaceAll("\"", "").toLowerCase().trim() === "i own the consequences of my actions");

  function day_of_week(date) {
      const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
      console.log(date);
      return days[new Date(`${date} 12:00pm`).getDay()];
  }

  function human_time(timestr) {
    let sp = timestr.split(':');
    const hour = parseInt(sp[0], 10);
    const h12 = (hour < 13) ? hour : hour % 12;
    const h = h12.toString().padStart(2, '0');
    const ap = (hour < 12) ? "AM" : "PM";
    console.log(h, sp[1], ap);
    return `${h}:${sp[1].trim()}${ap}`;
  }

  function candidate_times(session_duration) {
    let times = [];
    const max_hr = 22 - session_duration; // 10pm is close
    for (let hour = 10; hour <= max_hr; hour++) { // 10am is open
      for (let minute of (hour < max_hr) ? [0, 30] : [0]) {
        const h = hour.toString().padStart(2, '0');
        const m = minute.toString().padStart(2, '0');
        times.push(`${h}:${m}`);
      }
    }
    return times
  }

  let session = [];
  let selected = null;

  let running = false;
  async function select(cls_id) {
    let tmpl = (await templates)[cls_id];
    console.log(tmpl, templates, cls_id);
    selected = {
      id: cls_id,
      tmpl,
      starts: Array.from({ length: tmpl.hours.length || 1 }, (_, i) => {
          const date = new Date();
          date.setDate(date.getDate() + 14 + i);
          const ct = candidate_times(tmpl.hours[i]);
          const t = (ct.indexOf("18:00") === -1) ? ct.pop() : "18:00";
          return [date.toISOString().split('T')[0].slice(0, 10), t];
      }),
    };
    console.log("Selected class:", cls_id, templates, selected);
    do_validate();
  }

  function post_data() {
    const sessions = selected.starts.map(([date, time], i) => {
      console.log(date, time);
      // https://www.javaspring.net/blog/date-parsing-in-javascript-is-different-between-safari-and-chrome/#3-why-these-differences-exist-root-causes
      // Kind of a hacky way to create a date, but at least it's compatible and works for EST including DST (probably)
      const datestr = `${date}T${time}:00-0` + Math.floor(new Date().getTimezoneOffset() / 60) + ':00';
      console.log(datestr);
      const t1 = new Date(datestr);
      const t2 = new Date(t1.getTime() + selected.tmpl.hours[i] * 60 * 60 * 1000);
      console.log(t1, t2);
      return [isodatetime(t1), isodatetime(t2)];
    });
    console.log("cls_id " + selected.id + "; sessions ", sessions);
    return {
      cls_id: selected.id,
      sessions,
      skip_validation: ovr,
    };
  }

  const DEBOUNCE_MS = 1000;
  let debounce_timeout = null;
  let controller = new AbortController(); // For cancelling validation early
  function do_validate_debounced() {
    // This attempts to limit unnecessary validation work on the server, which should make things feel more responsive overall.
    // Requests are cancelled if a change is made while validation is in flight, and validation is only started
    // after DEBOUNCE_MS of idle time in making edits.
    if (controller) {
      controller.abort(); // If we're gonna trigger validation eventually, let's stop running any old validation
      controller = new AbortController();
    }
    if (debounce_timeout) {
      clearTimeout(debounce_timeout);
      debounce_timeout = null;
    }
    debounce_timeout = setTimeout(do_validate, DEBOUNCE_MS);
  }

  let validation_result = {valid: false, errors: []};
  function do_validate() {
    running = true;
    post("/instructor/validate?email=" + encodeURIComponent(email), post_data(), (controller) ? controller.signal : null).then((data) => {
      validation_result = {valid: data.valid, errors: data.errors};
    })
    .catch((err) => {
      if (err.toString().startsWith("AbortError")) {
        console.error(err); // Aborts are user-caused and shouldn't show warnings/issues
      } else {
        validation_result = {valid: false, errors: [`Validation request error: ${err}`, `Contact #software channel in Discord`]};
      }
    }).finally(() => running = false);
  }

  function save_schedule() {
    running = true;
    post("/instructor/push_class?email=" + encodeURIComponent(email), post_data()).then((rep) => {
      console.log(rep);
      if (rep.valid) {
        open = false;
      } else {
        validation_result = rep;
      }
    }).catch((err) => {
      validation_result = {valid: false, errors: [`Save error: ${err}`, `Contact #software channel in Discord`]};
    }).finally(() => running = false);
  }
</script>

<Modal size="lg" isOpen={open}>
  <ModalHeader>Class Scheduler</ModalHeader>
  <ModalBody>
    <h5>Select a class to schedule</h5>
    {#await templates}
        <Spinner/> Loading...
    {:then t}
    <Dropdown autoClose={true} class="my-3">
      <DropdownToggle caret>
          {#if !selected}
            {Object.keys(classes).length} option(s)
          {:else}
            {classes[selected.id]}
          {/if}
      </DropdownToggle>
      <DropdownMenu>
        {#each Object.entries(classes) as [cls_id, cls_name]}
          <DropdownItem on:click={() => select(cls_id)}>{cls_name}</DropdownItem>
        {/each}
      </DropdownMenu>
    </Dropdown>
    {#if selected }
      <div><strong>Session Hours:</strong> {selected.tmpl.hours.join(', ')}</div>
      <div><strong>Capacity:</strong> {selected.tmpl.capacity}</div>
      <div><strong>Price:</strong> ${selected.tmpl.price}</div>
      <div><strong>Min days between runs:</strong> {selected.tmpl.period}</div>
      <div><strong>Areas:</strong> {selected.tmpl.areas.join(', ')}</div>
      <div><strong>Clearances earned:</strong></div>
      {#if selected.tmpl.clearances.length > 0}
      <ListGroup>
        {#each selected.tmpl.clearances as clr}
        <ListGroupItem>{clr}</ListGroupItem>
        {/each}
      </ListGroup>
      {:else}
      None
      {/if}
      <h5>Select times for each session</h5>
      {#each selected.starts as _, i}
        <Row>
          <Col>
          {day_of_week(selected.starts[i][0])}
          </Col>
          <Col>
            <Input type="date" placeholder="Start" bind:value={selected.starts[i][0]} on:change={do_validate_debounced}/>
          </Col>
          <Col>
          <Dropdown autoclose={true}>
            <DropdownToggle caret>
              {human_time(selected.starts[i][1])}
            </DropdownToggle>
            <DropdownMenu class="dropdown-menu-scrollable">
              {#each candidate_times(selected.tmpl.hours[i]) as time}
                <DropdownItem on:click={() => {selected.starts[i][1] = time; do_validate_debounced()}} active={selected.starts[i][1] === time}>
                  {human_time(time)}
                </DropdownItem>
              {/each}
            </DropdownMenu>
          </Dropdown>
          </Col>
          <Col xs="auto">
              ({selected.tmpl.hours[i]}hr session)
          </Col>
        </Row>
      {/each}
    {/if}
    {:catch error}
      <Alert color="danger">{error.message.replace("Invalid reply from server: ", "")}</Alert>
    {/await}

    {#if validation_result.errors.length > 0}
      <h5 class="my-3">Validation errors found:</h5>
      <ListGroup>
      {#each validation_result.errors as e}
        <ListGroupItem color="warning">{e}</ListGroupItem>
      {/each}
      </ListGroup>

      {#if admin}
        <Input class="my-3" type="text" placeholder={"Type \"I own the consequences of my actions\" here to ignore all errors and proceed"} bind:value={validation_override} />
      {/if}
    {/if}
  </ModalBody>
  <ModalFooter>
    {#if running }<Spinner/>Validating....{/if}
    {#if !running && validation_result.valid}All validation checks passed <Icon name="check-all"/>{/if}
    {#if selected && !running && !validation_result.valid}Some validation checks failed <Icon name="exclamation-triangle"/>{/if}
    <Button on:click={save_schedule} disabled={!ovr && (running || !validation_result.valid)}>Save proposed classes</Button>
    <Button on:click={() => open = false} disabled={running}>Close</Button>
  </ModalFooter>
</Modal>

<style>
  h5 {
    margin-top: 20px;
  }
  .dropdown-menu-scrollable {
    max-height: 300px;
    overflow-y: auto;
  }
</style>
