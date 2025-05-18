<script type="typescript">
import { onMount } from 'svelte';
import {get, put, del, isodate, localtime, as_datetimelocal} from '$lib/api.ts';
import { Spinner, Table, Badge, Accordion, AccordionItem, FormGroup, InputGroup, InputGroupText, Label, Button, Modal, ModalHeader, ModalBody, ModalFooter, Popover, Input } from '@sveltestrap/sveltestrap';
import FetchError from '../fetch_error.svelte';
import CalendarEdit from '$lib/dashboard/calendar_edit.svelte';

export let inst;
export let inst_id;
export let start;
export let end;
export let date_edited;

let records = {};
let edit_rec = null;

function reload() {
  if (start && end && inst) {
    promise = get(`/instructor/calendar/availability?inst=${encodeURIComponent(inst)}&t0=${encodeURIComponent(start)}&t1=${encodeURIComponent(end)}`).then((data) => {
      records = data.records;

      let avail_lookup = {};
      for (let evt of data.availability) {
        let dstr = isodate(evt[1]);
        avail_lookup[dstr] = [...(avail_lookup[dstr] || []), evt];
      }

      let reservation_lookup = {};
      let idx = 0;
      for (let res of data.reservations) {
        let dstr = isodate(res[0]);
        reservation_lookup[dstr] = [...(reservation_lookup[dstr] || []), {
          idx,
          start: localtime(res[0]),
          end: localtime(res[1]),
          resource: res[2],
          name: res[3],
          url: res[4],
        }];
        idx += 1;
      }

      let sched_days = {}
      idx = 0;
      for (let sch of data.schedule) {
        for (let i = 0; i < sch['fields']['Days (from Class)'][0]; i++) {
          let d = new Date(sch['fields']['Start Time']);
          d.setDate(d.getDate() + 7*i);
          let sched = {
            idx,
            inst: sch['fields']['Instructor'],
            name: sch['fields']['Name (from Class)'],
            neon_id: sch['fields']['Neon ID']
          };
          sched.display = sched.inst.match(/\b(\w)/g).join(''); // Get initials of name
          if (!sched.neon_id) {
            sched.display = "*" + sched.display;
          }
          sched_days[isodate(d)] = [...(sched_days[isodate(d)] || []), sched];
          idx += 1
        }
      }

      let s = new Date(start);
      let d = new Date(start);
      d.setHours(12); // Select Noon to prevent DST bugs changing the date
      d.setDate(d.getDate() - d.getDay()); // Set to start of the week
      let e = new Date(end);

      let weeks = [];
      let darr = [];
      for (; d < s; d.setDate(d.getDate() + 1)) {
        let dstr = isodate(d);
        darr.push({'date': dstr, 'filler': true, 'events': []});
        if (darr.length >= 7) {
          weeks.push(darr);
          darr = [];
        }
      }

      for (; d <= e; d.setDate(d.getDate() + 1)) {
        let dstr = isodate(d);
        darr.push({
          'date': dstr,
          'events': avail_lookup[dstr] || [],
          'reservations': reservation_lookup[dstr] || [],
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
      console.log(result);
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


function save_avail(id, start, end, recurrence) {
    promise = put(`/instructor/calendar/availability`, {
    	inst_id,
    	rec: id,
      t0: start,
      t1: end,
      recurrence: recurrence,
    }).then(date_edited).then(reload).finally(() => {edit_rec = null});
    return promise;
}
function delete_avail(id) {
  promise = del(`/instructor/calendar/availability`, {'rec': id}).then(date_edited).then(reload).finally(() => edit_rec = null);
  return promise;
}

function start_edit(e, d) {
  e.stopPropagation();
  let r = records[d];
  if (r)  {
    edit_rec = {
    id: d,
    start: as_datetimelocal(r['Start']),
    end: as_datetimelocal(r['End']),
    recurrence: r['Recurrence'],
    };
  } else {
    edit_rec = {
    id: null,
    start: `${d}T18:00`,
    end: `${d}T21:00`,
    recurrence: "",
    };
  }
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

<Accordion flush stayOpen>
<AccordionItem header="Click here for legend">
<ul>
<li><Button style="display: block" color='secondary'>HH:MM A/P</Button>Available to schedule - click to edit</li>
<li><Badge color="primary">XX</Badge> Your scheduled class - click for info</li>
<li><Badge color="light">XX</Badge> Another instructors' scheduled class - click for info</li>
</ul>
</AccordionItem>
</Accordion>

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
			{d.date.substr(5)}
			{#if d.events.length > 0}

			{#each d.events as e}
			  <Button style="display:block" color={((edit_rec && edit_rec.id) === e[0]) ? 'primary' : 'secondary'} on:click={(evt) => {start_edit(evt, e[0])}}>{localtime(e[1])}</Button>
			{/each}
      {#if d.reservations.length > 0}
			  <Popover trigger="hover" target={"resrv"+d.reservations[0].idx}>
          {#each d.reservations as r}
              <div>{r.resource}</div>
              <div>{r.start} - {r.end}</div>
              <div><a href={r.url} target="_blank">Reserved by {r.name}</a></div>
          {/each}
        </Popover>
			<Badge id={"resrv"+d.reservations[0].idx} color={"warning"} target="_blank">{d.reservations.length} res</Badge>
      {/if}
			{#each d.schedule as s}
			  <Popover trigger="hover" target={"sched"+s.idx}>
          {#if s.neon_id}
            Scheduled: {s.name} with {s.inst} (#{s.neon_id})
          {:else}
            *Proposed but not yet scheduled: {s.name} with {s.inst}
          {/if}
        </Popover>
			  <Badge id={"sched"+s.idx} color={(s.inst === inst) ? "primary" : "light"}>{s.display}</Badge>
			{/each}
			{/if}
		</td>
		{/each}
	    </tr>
	  {/each}
	</tbody>

  </Table>
{:catch error}
  <FetchError {error}/>
{/await}
<CalendarEdit bind:rec={edit_rec} on_save={save_avail} on_delete={delete_avail}/>
