<script type="ts">
  import { Alert, Input, Image, Button, Row, Col, Card, CardHeader, CardTitle, CardBody, CardFooter, Spinner } from '@sveltestrap/sveltestrap';
  import { post } from '$lib/api.ts';
  import FetchError from '$lib/fetch_error.svelte';

  export let on_close;
  export let name;
  export let guest = false;
  export let radioGroup;
  export let announcements;
  export let violations;
  export let email;

  let count = 15;
  function updateTimer() {
    count = count - 1;
  }
  function extendTimer() {
    count = 45;
  }
  addEventListener('keypress', extendTimer);
  addEventListener('mousemove', extendTimer);

  function submitAnnouncementResponse(a) {
    a.submitting = true;
    a.submit_ok = false;
    announcements = announcements; // Force UI rerender
    a.promise = post('/welcome/survey_response', {
      rec_id: a.rec_id,
      email,
      response: a.response
    }).then(() => a.submit_ok = true).finally(() => {
      a.submitting = false;
      announcements = announcements; // Force UI rerender
    });
    return a.promise;
  }

  let interval = setInterval(updateTimer, 1000);
  $: if (count === 0) {clearInterval(interval); on_close(radioGroup);}
</script>

<Card>
  <Row class="text-center my-3">
  {#if !guest}
  <h2>Welcome, {name}!</h2>
  {#if announcements.length == 0 && violations.length == 0 }<p>You're all set!</p>{/if}
  {:else}
  <h2>Welcome guest!</h2>
  <p>You're all set! But if you have a moment, we'd appreciate your feedback...</p>
  {/if}
  </Row>

  {#if guest}
    <Row class="text-left justify-content-center my-3">
      <Col sm={{size: 'auto'}}>
      <h4>How did you hear about us?</h4>
      {#each ['Friend/colleague/family', 'Google search', 'Protohaven booth at community event', 'Social media', 'Legacy TechShop', 'Drove/biked/walked by', 'Gift', 'Other'] as value}
	<Input type="radio" bind:group={radioGroup} {value} label={value.charAt(0).toUpperCase() + value.slice(1)} />

      {/each}
      </Col>
    </Row>
  {/if}

  {#if violations.length > 0}
    <Alert color="warning">
    <h4 class="my-2 text-center">You have one or more active policy violations:</h4>
    {#each violations as v}
    <Card class="m-2">
      <CardHeader><CardTitle>{v.fields.Calculation}</CardTitle></CardHeader>
      <CardBody>
      	<p>Violations: <strong>{v.fields['Section (from Relevant Sections)']}</strong></p>
        <p>Notes: {v.fields.Notes}</p>
	{#if v.fields.Evidence}
	{#each v.fields.Evidence as e}
	  <Image thumbnail style="height: 150px !important;" src={e.thumbnails.large.url}/>
	{/each}
	{/if}
      </CardBody>
    </Card>
    {/each}
    <h4 class="text-center">Please see a shop tech or staff to resolve them.</h4></Alert>
  {/if}

  {#if announcements.length > 0 }
    {#each announcements as a}
    <Card class="m-2">
      <CardHeader><CardTitle>
        {#if a.Survey }
          <strong>Response Requested: </strong>
        {/if}
        {a.Title}
      </CardTitle></CardHeader>
      <CardBody>
      {a.Message}
      {#if a.Survey == 'Text' }
        <Input type="text" placeholder="(Optional) please type a response" bind:value={a.response} disabled={a.submitting || a.submit_ok}></Input>
      {/if}
      </CardBody>
      {#if a.Survey}
      <CardFooter>
        <Button on:click={() => submitAnnouncementResponse(a)} color="primary" disabled={a.submitting || a.submit_ok || !a.response}>Submit</Button>
        {#await a.promise}
          <Spinner/>
        {:then arep}
          {#if a.submit_ok}
            <em>Thanks for your response!</em>
          {/if}
        {:catch error}
          <FetchError {error} nohelp/>
        {/await}
      </CardFooter>
      {/if}
    </Card>
    {/each}
  {/if}

  <Row class="justify-content-center my-3 text-center">
    {#if count >= 0 && count < 20}
    <em>Going back to sign-in form in {count}...</em>
    {/if}
    <Col sm={{ size: 'auto'}}>
      <Button color='primary' on:click={() => {count = 0}}>Ok</Button>
    </Col>
  </Row>
</Card>
