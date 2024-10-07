<script type="typescript">

import { Modal, ModalBody, ModalFooter, Button, ListGroup, ListGroupItem, Input, Spinner } from '@sveltestrap/sveltestrap';
import {get, post, del} from '$lib/api.ts';
import FetchError from '../fetch_error.svelte';

export let edit = null; // obj with `date`, `ap`, `techs`, `orig`, `email`, `fullname`
export let all_techs = get("/techs/list").then((data) => {
  let tt = data.techs.map((t) => { return {name: t.name, shift: t.shift}});
  tt.sort((a,b) => a.name > b.name);
  return tt;
});
export let on_update;

function rm(tech) {
  edit.techs = edit.techs.filter((t) => t != tech);
}

let selected;
let custom_text;
function add_custom() {
  edit.techs.push(custom_text);
  edit = edit; // Trigger update
  custom_text = "";
  selected = "";
}
function selection_changed() {
  if (selected === "custom" || selected === "") {
    return;
  }
  edit.techs.push(selected);
  edit = edit; // Trigger update
  selected = "";
}

let promise = new Promise((resolve) => { resolve(null)});
let acting = false;
function save() {
  acting = true;
  promise = post("/techs/forecast/override", edit).then((result) => {
	edit = null;
	on_update();
  }).finally(() => acting = false);
}
function revert() {
  acting = true;
  promise = del("/techs/forecast/override", edit).then((result) => {
	edit = null;
	on_update();
  }).finally(() => acting = false);
}


</script>

<Modal isOpen={edit} header="Shift change: {edit && edit.date} {edit && edit.ap}">
<ModalBody>
  <ListGroup>
  {#if edit && edit.techs.length == 0}
    No techs on shift
  {/if}
  {#if edit.id}
	Original:
	  {#each edit.orig as t}
	    <ul>
	      <li>{t}</li>
	    </ul>
	  {/each}
      <hr/>
  {/if}
  {#each edit.techs as t}
    <ListGroupItem><Button on:click={() => rm(t)}>X</Button>{t}</ListGroupItem>
  {/each}
    <ListGroupItem>
      {#await all_techs}
	<Spinner/>
	{:then tt}
      <Input type="select" bind:value={selected} on:change={selection_changed}>
        <option value="">Add new...</option>
	  {#each tt as t}
	  <option value={t.name}>{t.name}{#if t.shift}&nbsp;(from {t.shift}){/if}</option>
	  {/each}
	<option value="custom">Custom...</option>
      </Input>
      {#if selected == 'custom'}
        <div class="d-flex flex-row">
        <Input type="text" bind:value={custom_text} placeholder="Custom Tech"/>
	<Button on:click={add_custom}>Add</Button>
	</div>
      {/if}
      {:catch  error}
	  <FetchError {error}/>
	{/await}
    </ListGroupItem>
  </ListGroup>
</ModalBody>
<ModalFooter>
  {#if edit.id}
  <div><em>Last edit: {edit.editor}</em></div>
  {/if}
  {#await promise}
   <Spinner/>
  {:catch error}
    <FetchError {error}/>
  {/await}
  <Button color="primary" on:click={save} disabled={acting}>Save</Button>
  {#if edit.id}
  <Button color="primary" on:click={revert} disabled={acting}>Revert</Button>
  {/if}
  <Button color="secondary" on:click={() => edit = null} disabled={acting}>Cancel</Button>
</ModalFooter>
</Modal>
