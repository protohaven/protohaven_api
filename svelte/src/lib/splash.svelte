<script type="ts">
  import { Button, Row, Col, Card, Input, Spinner, FormGroup } from '@sveltestrap/sveltestrap';
  import { onMount, onDestroy } from 'svelte';
  export let on_member;
  export let on_guest;
  export let feedback;
  export let email;
  export let checking;
  export let dependent_info;
  let has_dependents = false;

  async function reset() {
    email = "";
    checking = false;
    dependent_info = "";
    has_dependents = false;
  }
  reset();


  $: submit_enabled = (email != "" && !checking && !(has_dependents && dependent_info == ""));

  // Shortcut for members
  function check_enter_key_submit(e) {
    if (e.key == 'Enter') {
      on_member();
    }
  }

  // Inactivity timer - reset for the next person
  let count;
  let interval = null;
  function updateTimer() {
    count = count - 1;
    console.log(count);
  }
  function extendTimer() {
    if (interval === null) {
      interval = setInterval(updateTimer, 1000);
    }
    count = 60;
  }

  onMount(() => {
    addEventListener('keypress', extendTimer);
    addEventListener('mousemove', extendTimer);
  });
  onDestroy(() => {
    if (interval) clearInterval(interval);
  });

  $: if (count === 0) {clearInterval(interval); interval=null; reset();}
</script>

<Card>
  <Row>
    <Col class="text-center my-5">
      <h1>Welcome! Please sign in:</h1>
      <em>If you are a member, you must use the email that's linked to your membership.</em>
    </Col>
  </Row>

  <Row class="mx-5">
    <Col>
    <FormGroup>
      <Input type="email" disabled={checking} placeholder="Your email address here" bind:value={email} invalid={feedback !== null} {feedback} on:keydown={check_enter_key_submit} />
    </FormGroup>
    </Col>

    {#if checking}
      <Col sm={{size: 'auto'}}>
        <Spinner type="border" color="primary" />
      </Col>
    {/if}
  </Row>

  <Row class="justify-content-center">
    <Col sm={{ size: 'auto'}}>
      <Input bind:checked={has_dependents} type="checkbox" label="I am signing in one or more children under age 18" tabindex=-1 />
      {#if has_dependents}
      <Input type="email" disabled={checking} placeholder="Enter child name(s) here" bind:value={dependent_info} />
      {/if}
    </Col>
  </Row>

  <Row class="justify-content-center text-center mt-5">
    <h3>I am a...</h3>
  </Row>

  <Row class="d-flex justify-content-center my-3">
    <Col sm={{ size: 'auto'}} class="mr-3">
      <Button size='lg' disabled={!submit_enabled} color='primary' on:click={on_member}>Member</Button>
    </Col>
    <Col sm={{ size: 'auto'}}>
      <Button size='lg' disabled={!submit_enabled} color='light' on:click={on_guest}>Guest</Button>
    </Col>
  </Row>
</Card>
