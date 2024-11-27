<script type="typescript">
import { onMount } from 'svelte';
import {get, put, del, isodate, localtime, as_datetimelocal} from '$lib/api.ts';
import { Spinner, Table, Badge, Accordion, AccordionItem, FormGroup, InputGroup, InputGroupText, Label, Button, Modal, ModalHeader, ModalBody, ModalFooter, Popover, Input } from '@sveltestrap/sveltestrap';
import FetchError from '../fetch_error.svelte';

export let weeks; // a list of lists of {date, filler, body}
export let start_edit_fn;
</script>

<style>
  td {
    cursor: pointer;
  }
  td.filler {
    color: #ddd;
  }
</style>

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
  {#each weeks as w}
  <tr>
    {#each w as d}
    <td on:click={(evt) => start_edit_fn(evt, d.date)} class={(d.filler) ? "filler" : ""}>
      {d.body}
    </td>
    {/each}
  </tr>
  {/each}
</tbody>
</Table>
