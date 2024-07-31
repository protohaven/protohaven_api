<script type="ts">
import { onMount } from 'svelte';
import {get, put, del, isodate, localtime, as_datetimelocal} from '$lib/api.ts';
import { Spinner, Table, Badge, FormGroup, InputGroup, InputGroupText, Label, Button, Modal, ModalHeader, ModalBody, ModalFooter, Tooltip, Input } from '@sveltestrap/sveltestrap';
import FetchError from './fetch_error.svelte';

export let inst;
export let inst_id;
export let start;
export let end;
let open = false;

let avail_id = null;
let avail_start = null;
let avail_end = null;
let avail_interval = null;
let avail_interval_end = null;
let records = {};

function reload() {
  console.log("Reload triggered");
  if (start && end && inst) {
    let bounds = [new Date(start), new Date(end)]
    promise = get(`/instructor/calendar/availability?inst=${inst}&t0=${start}&t1=${end}`).then((data) => {
      let lookup = {};
      records = data.records;
      for (let evt of data.availability) {
        let dstr = isodate(evt[1]);
        lookup[dstr] = [...(lookup[dstr] || []), evt];
      }

      let sched_days = {}
      let idx = 0;
      for (let sch of data.schedule) {
        for (let i = 0; i < sch['fields']['Days (from Class)'][0]; i++) {
	  let d = new Date(sch['fields']['Start Time']);
	  d.setDate(d.getDate() + 7*i);
	  let sched = {
	  	idx,
	  	inst: sch['fields']['Instructor'],
		name: sch['fields']['Name (from Class)'],
	  };
	  console.log(sched);
	  sched.display = sched.inst.match(/\b(\w)/g).join(''); // Get initials of name
	  sched_days[isodate(d)] = [...(sched_days[isodate(d)] || []), sched];
	  idx += 1
	}
      }
      console.log(sched_days);

      let s = new Date(start);
      let d = new Date(start);
      d.setDate(d.getDate() - d.getDay() - 1); // Set to start of the week
      let e = new Date(end);

      let weeks = [];
      let darr = [];
      for (; d < s; d.setDate(d.getDate() + 1)) {
	let dstr = isodate(d);
	darr.push({'date': dstr, 'filler': true, 'events': []});
      }

      for (; d <= e; d.setDate(d.getDate() + 1)) {
	let dstr = isodate(d);
	darr.push({
	  'date': dstr,
	  'events': lookup[dstr] || [],
	  'schedule': sched_days[dstr] || []
	});
	if (darr.length >= 7) {
	  weeks.push(darr);
	  darr = [];
	}
      }
      if (darr.length >= 0) {
	 weeks.push(darr);
      }
      let result = {'start': new Date(start), 'end': e, weeks, 'events': data.records};
      return result;
    });
  }
}
$: {
  if (start && end) {
    reload();
  }
}
onMount(reload);

let promise = Promise.resolve((resolve, reject)=>{resolve([])});

function start_edit(e, d) {
	let r = records[d];
	if (r) {
	  avail_id = d;
	  avail_start = as_datetimelocal(r['Start']);
	  avail_end = as_datetimelocal(r['End']);
	  avail_interval = r['Interval'];
	  avail_interval_end = null;
	  if (r['Interval End']) {
	  	avail_interval_end = isodate(r['Interval End']);
	  }
	} else {
	  avail_id = null;
	  avail_start = `${d}T18:00`;
	  avail_end = `${d}T21:00`;
	  avail_interval = null;
	  avail_interval_end = null;
	}
	e.stopPropagation();
	open = true;
}

function save_avail() {
    promise = put(`/instructor/calendar/availability`, {
    	inst_id,
    	rec: avail_id,
	t0: avail_start,
	t1: avail_end,
	interval: avail_interval,
	interval_end: avail_interval_end
    }).then(reload).finally(() => {
	open = false;
    });
}
function delete_avail() {
  promise = del(`/instructor/calendar/availability`, {rec: avail_id}).then(reload).finally(() => open = false);
}
</script>

<style>
  td {
    cursor: pointer;
  }
  td.filler {
    color: #ddd;
  }
</style>

{#await promise}
  <Spinner/>
{:then p}
  <Table bordered>
  	<thead>
	<tr>
	<th>Su</th>
	<th>Mo</th>
	<th>Tu</th>
	<th>We</th>
	<th>Th</th>
	<th>Fr</th>
	<th>Sa</th>
	</tr>
	</thead>
	<tbody>
	  {#each p.weeks as w}
	    <tr>
		{#each w as d}
		<td on:click={(evt) => start_edit(evt, d.date)} class={(d.filler) ? "filler" : ""}>
			{#if d.events.length > 0}
			{#each d.events as e}
			  <Button style="display:block" color={(avail_id === e[0]) ? 'primary' : 'secondary'} on:click={(evt) => {console.log('se', e[0]); start_edit(evt, e[0])}}>{localtime(e[1])}</Button>
			{/each}
			{#each d.schedule as s}
			  <Tooltip target={"sched"+s.idx}>Scheduled: {s.name} with {s.inst}</Tooltip>
			  <Badge id={"sched"+s.idx} color={(s.inst === inst) ? "primary" : "light"}>{s.display}</Badge>
			{/each}
			{:else}
			{d.date.substr(5)}
			{/if}
		</td>
		{/each}
	    </tr>
	  {/each}
	</tbody>

  </Table>
  <Modal size="md" isOpen={open}>
	<ModalHeader>Add/Edit Availability</ModalHeader>
	<ModalBody>
		<FormGroup>
			<Label>Availability</Label>
			<InputGroup>
				<InputGroupText>Start</InputGroupText>
				<Input type="datetime-local" bind:value={avail_start}/>
			</InputGroup>
			<InputGroup>
				<InputGroupText>End</InputGroupText>
				<Input type="datetime-local" bind:value={avail_end}/>
			</InputGroup>
		</FormGroup>
		<FormGroup>
			<Label>Optional</Label>
			<InputGroup>
				<InputGroupText>Repeat Every</InputGroupText>
    				<Input type="number" bind:value={avail_interval}/>
				<InputGroupText>Day(s)</InputGroupText>
			</InputGroup>
			<InputGroup>
				<InputGroupText>Until</InputGroupText>
    				<Input type="date" bind:value={avail_interval_end}/>
			</InputGroup>
		</FormGroup>
	</ModalBody>
	<ModalFooter>
	    <Button on:click={save_avail}>Save</Button>
	    <Button on:click={delete_avail} disabled={!avail_id}>Delete</Button>
	    <Button on:click={() => open = false}>Cancel</Button>
	</ModalFooter>
  </Modal>
{:catch error}
  <FetchError {error}/>
{/await}
