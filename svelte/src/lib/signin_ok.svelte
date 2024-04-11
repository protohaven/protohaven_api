<script type="ts">
  import { Input, Button, Row, Col, Card, CardHeader, CardTitle, CardBody } from '@sveltestrap/sveltestrap';

  export let on_close;
  export let name;
  export let guest = false;
  export let radioGroup;
  export let announcements;

  let count = 15;
  function updateTimer() {
    count = count - 1;
  }
  function extendTimer() {
    count = 45;
  }
  addEventListener('keypress', extendTimer);
  addEventListener('mousemove', extendTimer);

  let interval = setInterval(updateTimer, 1000);
  $: if (count === 0) {clearInterval(interval); on_close(radioGroup);}
</script>

<Card>
  <Row class="text-center my-3">
  {#if !guest }
  <h2>Welcome, {name}!</h2>
  <p>You're all set!</p>
  {:else}
  <h2>Welcome guest!</h2>
  <p>You're all set! But if you have a moment, we'd appreciate your feedback...</p>
  {/if}
  </Row>

  {#if guest}
    <Row class="text-left justify-content-center my-3">
      <Col sm={{size: 'auto'}}>
      <h4>How did you hear about us?</h4>
      {#each ['Friend/colleauge/family', 'Google search', 'Protohaven booth at community event', 'Social media', 'Legacy TechShop', 'Drove/biked/walked by', 'Gift', 'Other'] as value}
	<Input type="radio" bind:group={radioGroup} {value} label={value.charAt(0).toUpperCase() + value.slice(1)} />

      {/each}
      </Col>
    </Row>
  {/if}

  {#if announcements.length > 0 }
    <h4 class="my-4 text-center">Announcements</h4>
    {#each announcements as a}
    <Card class="m-2">
      <CardHeader><CardTitle>{a.Title}</CardTitle></CardHeader>
      <CardBody>{a.Message}</CardBody>
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
