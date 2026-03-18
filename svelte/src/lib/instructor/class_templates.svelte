<script type="typescript" lang="ts">
import { Spinner, Table, Card, CardHeader, CardTitle, CardBody, Accordion, AccordionItem } from '@sveltestrap/sveltestrap';
import FetchError from '$lib/fetch_error.svelte';
import type { ClassTemplate } from './types';

export let visible: boolean;
export let data: { classes?: ClassTemplate[] } | null = null;

let class_templates: ClassTemplate[] = [];
let loading = false;
let error: Error | null = null;

// Process data when it becomes available
$: {
  if (data) {
    class_templates = data.classes || [];
    loading = false;
  }
}
</script>

{#if visible}
  <Card>
    <CardHeader>
      <CardTitle>Class Templates</CardTitle>
    </CardHeader>
    <CardBody>
      <p>This is a list of class <em>templates</em>, i.e. the metadata used to schedule classes.</p>
      <p>It does not reflect what classes are actually scheduled for registration - for this, see <a href="/events" target="_blank">/events</a>.</p>

      {#if !data}
        <Spinner/>
        <strong>Loading class templates...</strong>
      {:else if error}
        <FetchError {error}/>
      {:else}
        <Table bordered>
          <thead>
            <tr>
              {#each ["Name", "Approved?", "Schedulable?", "Timing", "Period", "Capacity", "Supply Cost", "Total Price"] as h}
                <th>{h}</th>
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each class_templates as c}
              <tr>
                <td>{c.name}</td>
                <td>{c.approved ? "Y" : "N"}</td>
                <td>{c.schedulable ? "Y" : "N"}</td>
                <td>{c.hours}</td>
                <td>{c.period}</td>
                <td>{c.capacity} student(s)</td>
                <td>${c.supply_cost}</td>
                <td>${c.price}</td>
              </tr>
            {/each}
          </tbody>
        </Table>
      {/if}
    </CardBody>
  </Card>
{/if}
