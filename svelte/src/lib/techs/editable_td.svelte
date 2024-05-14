<script type="ts">
  import { Icon, Input, Button } from '@sveltestrap/sveltestrap';

  export let value;
  export let enabled;
  let new_value;
  let editing = false;
  export let on_change;

  function edit_start() {
    console.log("Start editing");
    editing = true;
    new_value = value;
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
</script>

{#if editing}
<td>
  <div class="d-flex flex-row justify-content-between">
  <Input text bind:value={new_value}/>
  <div class="mx-2" on:click={edit_ok}><Icon name="check2-square"/></div>
  <div class="mx-2" on:click={edit_cancel}><Icon name="x-square"/></div>
  </div>
</td>
{:else}
<td>
  <div class="d-flex justify-content-between">
  <div class="mx-3">{value || ''}</div>
  {#if enabled}
  <Button class="ml-1" outline on:click={edit_start}><Icon name="pencil-square"/></Button>
  {/if}
  </div>
</td>
{/if}
