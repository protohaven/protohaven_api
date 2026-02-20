<script type="typescript">
  import '../../app.scss';
  import { onMount } from 'svelte';
  import {get, post} from '$lib/api.ts';

  import FetchError from '$lib/fetch_error.svelte';
  import {Spinner, ListGroup, ListGroupItem, Card, CardHeader, CardBody, CardTitle } from '@sveltestrap/sveltestrap';

  export let visible;
  export let rc;
  let promise = new Promise(()=>{});
  onMount(() => {
	  promise = get("/class_listing");
  });
</script>

{#if visible && rc}
  <Card class="my-3">
  <CardHeader>
        <CardTitle>Recertification</CardTitle>
  </CardHeader>
  <CardBody>
          <h5 style="my-3">Pending Recertifications:</h5>
          <div>Recertification is a work in progress, estimated to roll out in 2026.</div>
          <div><strong>For more info on the recertification process, see <a href="https://wiki.protohaven.org/books/policies/page/tool-recertification" target="_blank">our wiki</a>.</strong></div>
          {#if rc.pending.length > 0}
          <em>Note: If you need to recertify multiple tools of the same type (e.g., Laser 1 and Laser 2), you may only need to take one quiz for all of them. This is typically indicated on the first page of the online quiz.</em>
          <ListGroup>
          {#each rc.pending as pend}
            <ListGroupItem color={(new Date(pend[1]) > new Date()) ? "warning" : "danger"}>
              <strong>{pend[2].tool_name}</strong> -
              {#if pend[2].quiz_url}<a href={pend[2].quiz_url} target="_blank">Quiz Needed</a>
              {:else}
                <a href="https://form.asana.com/?k=YXgO7epJe3brNGLS6sOw7A&d=1199692158232291" target="_blank">Instruction Needed</a>
              {/if}
              by {pend[1]}
            </ListGroupItem>
          {/each}
          </ListGroup>
          {:else}
            <p><em>No recertification needed at this time.</em></p>
          {/if}
          <br>
          <h5 style="my-3">All Tool Recertifications</h5>
          <Accordion stayOpen>
          <AccordionItem header="Click Here for All Tool Recertifications">
          <p><em>This page lists tools requiring recertification and their specific processes.</em></p>
          <p><em>Tool clearances are granted only after an instructor verifies safe usage through classes or private instruction. Quizzes serve for recertification only after initial clearance is earned.</em></p>
          {#each rc.configs as cfg}
            <Card style="my-3">
            <CardHeader><strong>{cfg.tool}: {cfg.tool_name}</strong></CardHeader>
            <CardBody>
            <p>Process: {cfg.humanized}</p>
            {#if cfg.quiz_url}
            <p>Quiz URL: <a href={cfg.quiz_url} target="_blank">Click Here</a></p>
            {/if}
            </CardBody>
            </Card>
          {/each}
          </AccordionItem>
          </Accordion>
  </CardBody>
  </Card>
{/if}
