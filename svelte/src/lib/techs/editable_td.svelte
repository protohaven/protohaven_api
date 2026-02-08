<script type="typescript">
  import { Col, Row, Icon, Input, Button } from '@sveltestrap/sveltestrap';

  export let title: string;
  export let value: string;
  export let enabled: boolean;
  export let on_change: (value: string) => void;

  let new_value: string;
  let editing = false;
  let input_elem: HTMLInputElement;

  function edit_start() {
    editing = true;
    new_value = value;
    setTimeout(() => input_elem.focus(), 0);
  }

  function edit_cancel() {
    editing = false;
    new_value = "";
  }

  function edit_ok() {
    editing = false;
    value = new_value;
    new_value = "";
    on_change(value);
  }

  function check_for_submit(e: KeyboardEvent) {
    if (e.key === "Enter" || e.keyCode === 13) {
      edit_ok();
    }
  }
</script>

<div style:display={(editing) ? "inherit" : "none"}>
  <Row>
    <div class="d-flex flex-row justify-content-between">
      {#if title}<strong>{title}</strong>{/if}
      <Input
        text
        bind:value={new_value}
        bind:inner={input_elem}
        on:keypress={check_for_submit}
        aria-label={`Edit ${title}`}
      />
      <div class="mx-2" on:click={edit_ok} aria-label="Save changes">
        <Icon name="check2-square"/>
      </div>
      <div class="mx-2" on:click={edit_cancel} aria-label="Cancel editing">
        <Icon name="x-square"/>
      </div>
    </div>
  </Row>
</div>
<div style:display={(!editing) ? "inherit" : "none"}>
  <Row>
    <div class="d-flex justify-content-between">
      {#if title}<strong>{title}</strong>{/if}
      <div class="mx-3">{value || ''}</div>
      {#if enabled}
        <Button class="ml-1" outline on:click={edit_start} aria-label={`Edit ${title}`}>
          <Icon name="pencil-square"/>
        </Button>
      {/if}
    </div>
  </Row>
</div>
