<script type="typescript">
  import { Dropdown, DropdownMenu, DropdownItem, DropdownToggle, Row, Col, Button, Badge, Icon, Input, Modal, ModalHeader, ModalBody, ModalFooter, Spinner, ListGroup, Accordion, AccordionItem, ListGroupItem, Alert } from '@sveltestrap/sveltestrap';
  import { onMount } from 'svelte';
  import Calendar from '$lib/instructor/calendar.svelte';
  import {get, post, isodatetime} from '$lib/api.ts';
  export let open;
  export let inst;
  export let inst_id;
  export let templates = {};
  export let classes = {};


  function day_of_week(date) {
      const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
      console.log(date);
      return days[new Date(`${date} 12:00pm`).getDay()];
  }

  function candidate_times(session_duration) {
    let times = [];
    const max_hr = 22 - session_duration
    for (let hour = 10; hour <= max_hr; hour++) {
      for (let minute of (hour < max_hr) ? [0, 30] : [0]) {
        const h12 = (hour < 13) ? hour : hour % 12;
        const h = h12.toString().padStart(2, '0');
        const m = minute.toString().padStart(2, '0');
        const ap = (hour < 12) ? "AM" : "PM";
        times.push(`${h}:${m}${ap}`);
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
      starts: Array.from({ length: tmpl.days || 0 }, (_, i) => {
          const date = new Date();
          date.setDate(date.getDate() + 14 + i);
          return [date.toISOString().split('T')[0].slice(0, 10), "6:00pm"];
      }),
    };
    console.log("Selected class:", cls_id, templates, selected);
    do_validate();
  }

  function post_data() {
    const sessions = selected.starts.map(([date, time]) => {
      console.log(date, time);
      const t1 = new Date(`${date} ${time}`);
      const t2 = new Date(t1.getTime() + selected.tmpl.hours * 60 * 60 * 1000);
      console.log(t1, t2);
      return [isodatetime(t1), isodatetime(t2)];
    });
    console.log("cls_id " + selected.id + "; sessions ", sessions);
    return {
      cls_id: selected.id,
      sessions,
    };
  }

  let validation_result = {valid: false, errors: []};
  function do_validate() {
    running = true;
    post("/instructor/validate", post_data()).then((data) => {
      validation_result = {valid: data.valid, errors: data.errors};
    })
    .catch((err) => {
      validation_result = {valid: false, errors: [`Validation request error: ${err}`, `Contact #software channel in Discord`]};
    }).finally(() => running = false);
  }

  function save_schedule() {
    post("/instructor/push_class", post_data()).then((rep) => {
      console.log(rep);
      open = false;
    }).catch((err) => {
      validation_result = {valid: false, errors: [`Save error: ${err}`, `Contact #software channel in Discord`]};
    }).finally(() => running = false);;
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
      <div><strong>Sessions:</strong> {selected.tmpl.days}</div>
      <div><strong>Hours per session:</strong> {selected.tmpl.hours}</div>
      <div><strong>Capacity:</strong> {selected.tmpl.capacity}</div>
      <div><strong>Price:</strong> ${selected.tmpl.price}</div>
      <div><strong>Min days between runs:</strong> {selected.tmpl.period}</div>
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
            <Input type="date" placeholder="Start" bind:value={selected.starts[i][0]} on:change={do_validate}/>
          </Col>
          <Col>
          <Dropdown autoclose={true}>
            <DropdownToggle caret>
              {selected.starts[i][1]}
            </DropdownToggle>
            <DropdownMenu class="dropdown-menu-scrollable">
              {#each candidate_times(selected.tmpl.hours) as time}
                <DropdownItem on:click={() => selected.starts[i][1] = time} active={selected.starts[i][1] === time}>
                  {time}
                </DropdownItem>
              {/each}
            </DropdownMenu>
          </Dropdown>
          </Col>
          <Col xs="auto">
              ({selected.tmpl.hours}hr session)
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
    {/if}
  </ModalBody>
  <ModalFooter>
    {#if running }<Spinner/>Running....{/if}
    {#if !running && validation_result.valid}All validation checks passed <Icon name="check-all"/>{/if}
    {#if selected && !running && !validation_result.valid}Some validation checks failed <Icon name="exclamation-triangle"/>{/if}
    <Button on:click={save_schedule} disabled={running || !validation_result.valid}>Save proposed classes</Button>
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
