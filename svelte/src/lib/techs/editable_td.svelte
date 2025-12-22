<script type="typescript">
  import { Col, Row, Icon, Input, Button } from '@sveltestrap/sveltestrap';

  export let title;
  export let value;
  export let enabled;
  let new_value;
  let editing = false;
  let input_elem;
  export let on_change;

  function edit_start() {
    console.log("Start editing");
    editing = true;
    new_value = value;
    console.log(input_elem);
    setTimeout(() => input_elem.focus(), 0);
  }
  function edit_cancel() {
    editing = false;
    new_value = null;
  }
  function edit_ok() {
    editing = false;
    value = new_value;
    new_value = null;
    on_change(value);
  }
  function check_for_submit(e) {
    if (e.key === "Enter" || e.keyCode === 13) {
      edit_ok();
    }
  }
</script>

<div style:display={(editing) ? "inherit" : "none"}>
<Row>
  <div class="d-flex flex-row justify-content-between">
  {#if title}<strong>{title}</strong>{/if}
  <Input text bind:value={new_value} bind:inner={input_elem} on:keypress={check_for_submit}/>
  <div class="mx-2" on:click={edit_ok}><Icon name="check2-square"/></div>
  <div class="mx-2" on:click={edit_cancel}><Icon name="x-square"/></div>
  </div>
</Row>
</div>
<div style:display={(!editing) ? "inherit" : "none"}>
<Row>
  <div class="d-flex justify-content-between">
  {#if title}<strong>{title}</strong>{/if}
  <div class="mx-3">{value || ''}</div>
  {#if enabled}
  <Button class="ml-1" outline on:click={edit_start}><Icon name="pencil-square"/></Button>
  {/if}
  </div>
</Row>
</div>
