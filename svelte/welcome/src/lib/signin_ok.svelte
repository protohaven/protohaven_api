<script type="ts">
  import { Input, Button, Row, Col, Card } from '@sveltestrap/sveltestrap';

  export let on_close;
  export let name;
  export let guest = false;
  export let radioGroup;

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

  <Row class="text-left justify-content-center my-3">
  {#if guest}
    <Col sm={{size: 'auto'}}>
    <h4>How did you hear about us?</h4>
    {#each ['Friend/colleauge/family', 'Google search', 'Protohaven booth at community event', 'Social media', 'Legacy TechShop', 'Drove/biked/walked by', 'Gift', 'Other'] as value}
      <Input type="radio" bind:group={radioGroup} {value} label={value.charAt(0).toUpperCase() + value.slice(1)} />

    {/each}
    </Col>
  {/if}
  </Row>

  <Row class="justify-content-center my-3">
    {#if count >= 0 && count < 20}
    <em>Going back to sign-in form in {count}...</em>
    {/if}
    <Col sm={{ size: 'auto'}}>
      <Button color='primary' on:click={() => {count = 0}}>Ok</Button>
    </Col>
  </Row>
</Card>
