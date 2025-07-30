<script type="typescript">
import { Spinner, ListGroup, ListGroupItem, Table, Card, CardHeader, CardTitle, CardBody, Accordion, AccordionItem} from '@sveltestrap/sveltestrap';
import FetchError from '$lib/fetch_error.svelte';
import { onMount } from 'svelte';
import {get} from '$lib/api.ts';

let admin_data = new Promise((res,rej)=>{});
onMount(() => {
  admin_data = get("/instructor/admin_data");
});
</script>

<style>
  main {
    width: 80%;
    margin-left: auto;
    margin-right: auto;
    padding: 15px;
  }
</style>

<main>
<Card>
  <CardHeader><CardTitle>Admin Panel</CardTitle></CardHeader>
{#await admin_data}
  <Spinner/>
  <strong>Resolving admin data...</strong>
{:then p}
  <CardBody>
    <Accordion flush stayOpen>
        <AccordionItem header="Instructors">
        <p>Instructor data is fetched from Airtable - currently read-only pending further development.</p>
        <p>Contact the Software Dev team via Discord if you need to make a change to anything listed here.</p>
        <ListGroup>
        {#each p.capabilities as inst}
          <ListGroupItem>
            <p>Name: {inst.name}</p>
            <p>Active: {inst.active}</p>
            <p>Email: {inst.email}</p>
            <a href={"/instructor?email=" + encodeURIComponent(inst.email)} target="_blank">View their instructor page</a>
          </ListGroupItem>
        {/each}
        </ListGroup>
        </AccordionItem>
        <AccordionItem header="Class Templates">
          <p>This is a list of class <em>templates</em>, i.e. the metadata used to schedule classes.<p>
          <p>It does not reflect what classes are actually scheduled for registration - for this, see <a href="/events" target="_blank">/events</a>.</p>
        <Table bordered>
          <thead>
            <tr>{#each ["Name", "Approved?", "Schedulable?", "Timing", "Period", "Capacity", "Supply Cost", "Total Price"] as h}<th>{h}</th>{/each}</tr>
          </thead>
          <tbody>
            {#each p.classes as c}
              <tr>
                <td>{c.name}</td>
                <td>{c.approved ? "Y" : "N"}</td>
                <td>{c.schedulable ? "Y" : "N"}</td>
                <td>{c.hours}h{#if c.days > 1}, {c.days}d {c.recurrence}{/if}</td>
                <td>{c.period}</td>
                <td>{c.capacity} student(s)</td>
                <td>${c.supply_cost}</td>
                <td>${c.price}</td>
              </tr>
            {/each}
          </tbody>
        </Table>
        </AccordionItem>
    </Accordion>
  </CardBody>
{:catch error}
  <FetchError {error}/>
{/await}
</Card>
</main>
