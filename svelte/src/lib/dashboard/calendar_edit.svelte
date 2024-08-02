<script type="ts">
import { Spinner, Table, Badge, Accordion, AccordionItem, FormGroup, InputGroup, InputGroupText, Label, Button, Modal, ModalHeader, ModalBody, ModalFooter, Tooltip, Input } from '@sveltestrap/sveltestrap';
import { isodate, parse_8601_basic, isodatetime } from '$lib/api.ts';

// Had to reimplement rrule parsing here as the "canonical" rrule npm package does not work in this svelte environment
function expand(rr, start) {
   const days = [
   'Sunday',
   'Monday',
   'Tuesday',
   'Wednesday',
   'Thursday',
   'Friday',
   'Saturday',
   ];
   rr = rr.replace("RRULE:", "");
   let result = {
        start,
	dayOfWeek: "Unknown",
	recurrence: "",
	until: null,
	weekly: {
	  SU: false,
	  MO: false,
	  TU: false,
	  TH: false,
	  FR: false,
	  SA: false,
	},
   };
   if (start) {
 	result.dayOfWeek = days[(new Date(start)).getDay()];
   }
   for (let line of rr.split(';')) {
	let kv = line.split('=');
	if (kv[0] == 'FREQ') {
	  result.recurrence = kv[1];
	} else if (kv[0] == 'BYDAY') {
	  for (let d of kv[1].split(',')) {
	  	result.weekly[d.trim()] = true;
	  }
	} else if (kv[0] == 'UNTIL') {
	  result.until = isodate(parse_8601_basic(kv[1]));
	}
   }
   expanded = result;
}

export let rec;
let expanded;

export let on_save;
export let on_delete;

let dow = "Unknown";
$: {
  if (rec) {
    expand(rec.recurrence || '', rec.start);
  }
}


function do_save() {
  // Convert rec and expanded back to rrule format
  let rules = [];
  if (expanded.recurrence) {
    rules.push('FREQ=' + expanded.recurrence);
  }
  if (expanded.until) {
    rules.push('UNTIL=' + isodatetime(expanded.until).replace(/[-:\s]/g, ''));
  }
  if (expanded.recurrence == 'WEEKLY') {
    rules.push("BYDAY=" + Object.keys(expanded.weekly).filter(key => expanded.weekly[key]).join(','));
  }
  let rrule = 'RRULE:' + rules.join(';');
  //console.log(rec.id, rec.start, rec.end, rrule);
  on_save(rec.id, rec.start, rec.end, rrule);
}

</script>


  <Modal size="md" isOpen={rec}>
	<ModalHeader>Add/Edit Availability</ModalHeader>
	<ModalBody>
		<FormGroup>
			<Label>Availability</Label>
			<InputGroup>
				<InputGroupText>Start</InputGroupText>
				<Input type="datetime-local" bind:value={rec.start}/>
			</InputGroup>
			<InputGroup>
				<InputGroupText>End</InputGroupText>
				<Input type="datetime-local" bind:value={rec.end}/>
			</InputGroup>
		</FormGroup>
		<FormGroup>
			<InputGroup>
				<Input type="select" bind:value={expanded.recurrence}>
				  <option value="">Does Not Repeat</option>
				  <option value="DAILY">Daily</option>
				  <option value="WEEKLY">Weekly</option>
				  <option value="MONTHLY">Monthly</option>
				</Input>
			</InputGroup>
			{#if expanded.recurrence=="WEEKLY"}
			<Input type="checkbox" bind:checked={expanded.weekly.SU} label="Sunday"></Input>
			<Input type="checkbox" bind:checked={expanded.weekly.MO} label="Monday"></Input>
			<Input type="checkbox" bind:checked={expanded.weekly.TU} label="Tuesday"></Input>
			<Input type="checkbox" bind:checked={expanded.weekly.WE} label="Wednesday"></Input>
			<Input type="checkbox" bind:checked={expanded.weekly.TH} label="Thursday"></Input>
			<Input type="checkbox" bind:checked={expanded.weekly.FR} label="Friday"></Input>
			<Input type="checkbox" bind:checked={expanded.weekly.SA} label="Saturday"></Input>
			{/if}

			<InputGroup>
				<InputGroupText>Until</InputGroupText>
				<Input type="date" bind:value={expanded.until}/>
			</InputGroup>
		</FormGroup>
	</ModalBody>
	<ModalFooter>
	    <Button on:click={do_save}>Save</Button>
	    <Button on:click={() => on_delete(rec.id)} disabled={!(rec && rec.id)}>Delete</Button>
	    <Button on:click={() => rec = null}>Cancel</Button>
	</ModalFooter>
  </Modal>
