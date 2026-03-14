<script type="typescript">

import {onMount} from 'svelte';
import { FormGroup, Label, Accordion, AccordionItem, ListGroup, ListGroupItem, Button, Card, CardHeader, CardTitle, CardSubtitle, CardBody, Input, Spinner, Dropdown, DropdownToggle, DropdownMenu, DropdownItem, Toast, ToastBody, ToastHeader } from '@sveltestrap/sveltestrap';

import FetchError from '../fetch_error.svelte';
import {get, isodate, post} from '$lib/api.ts';


let start_date = new Date();
let end_date = new Date();

export let visible;
let search = "";
let search_term = "";
let search_results = [];
let searching = false;
let search_promise = Promise.resolve([]);
let selected_member = null;
let promise = new Promise((r,_)=>{r([])});
let loaded = false;
let toast_msg = null;

// Debounce function for search
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

const debouncedSearch = debounce(() => {
  if (!search_term.trim()) {
    search_results = [];
    return;
  }

  searching = true;
  search_promise = post(`/neon_lookup?search=${encodeURIComponent(search_term)}`)
    .then((results) => {
      search_results = results;
    })
    .catch((err) => {
      console.error("Search failed:", err);
      search_results = [];
      toast_msg = {
        color: 'danger',
        msg: 'Failed to search Neon accounts',
        title: 'Search Error'
      };
    })
    .finally(() => {
      searching = false;
    });
}, 300);

function search_neon_accounts() {
  debouncedSearch();
}

function refresh() {
  const start = isodate(new Date(start_date));
  const end = isodate(new Date(end_date));
  promise = get(`/techs/members?start=${start}&end=${end}`).then((data) => {
    loaded = true;
    let by_email = {};
    for (let d of data) {
      d.created = new Date(d.created);
      if (!by_email[d['email']]) {
        by_email[d['email']] = {...d, "timestamps": new Set()};
      }
      by_email[d['email']]['timestamps'].add(d.created.toLocaleTimeString());
    }
    let results = Object.values(by_email);
    // Sort descending, newest on top
    results.sort((a, b) => b.created - a.created);

    // Filter by selected member if one is selected
    if (selected_member) {
      results = results.filter(r => r.email === selected_member.email);
    }

    return results;
  });
}

function on_search_term_edit(e) {
  if (search_term !== `${selected_member?.name} (${selected_member?.email})`) {
    search_neon_accounts();
  } else {
    search_results = [];
    selected_member = null;
  }
}

function clear_selection() {
  selected_member = null;
  search_term = "";
  search_results = [];
  refresh();
}

$: {
  if (visible && !loaded) {
    refresh();
  }
}

</script>

{#if visible}
<Card>
<CardHeader>
  <CardTitle>Member Check</CardTitle>
  <CardSubtitle>Today's sign-ins, including membership state and clearances</CardSubtitle>
</CardHeader>
<CardBody>
    <div class="row">
      <div class="col-md-6">
        <FormGroup>
          <Label>Start Date</Label>
          <Input type="date" bind:value={start_date} on:change={refresh}/>
        </FormGroup>
      </div>
      <div class="col-md-6">
        <FormGroup>
          <Label>End Date</Label>
          <Input type="date" bind:value={end_date} on:change={refresh}/>
        </FormGroup>
      </div>
    </div>

    <FormGroup>
      <Label>Search Member</Label>
      <div class="position-relative">
        <div class="d-flex align-items-center">
          <Input
            type="text"
            bind:value={search_term}
            on:keydown={on_search_term_edit}
            placeholder="Search by name or email"
            aria-label="Search members by name or email"
          />
          {#if searching}
            <Spinner size="sm" class="ms-2"/>
          {/if}
          {#if selected_member}
            <Button color="secondary" size="sm" class="ms-2" on:click={clear_selection}>
              Clear
            </Button>
          {/if}
        </div>

        {#if search_results.length > 0}
          <div
            class="position-absolute bg-white border rounded shadow mt-1"
            style="z-index: 1000; width: 100%; max-height: 300px; overflow-y: auto;"
          >
            <ListGroup flush>
              {#each search_results as result}
                <ListGroupItem
                  tag="button"
                  action
                  on:click={() => {
                    selected_member = result;
                    search_term = `${selected_member.name} (${selected_member.email})`;
                    search_results = [];
                    refresh();
                  }}
                  class="text-start"
                >
                  {result.name} ({result.email})
                </ListGroupItem>
              {/each}
            </ListGroup>
          </div>
        {/if}
      </div>
      <small class="form-text text-muted">
        {#if selected_member}
          Showing sign-in history for {selected_member.name} only
        {:else}
          Showing all members who signed in on selected date
        {/if}
      </small>
    </FormGroup>

    {#await promise}
      <Spinner/>Loading...
    {:then p}
    <ListGroup>
    {#each p as r}
      <ListGroupItem>
        <p><strong>{r.email}{#if r.name}&nbsp;({r.name}){/if}</strong>
          {r.created.toLocaleTimeString()} -
              {#if !r.member}
                Guest
              {:else}
                  Member (<span style={(r.status !== 'Active') ? 'background-color: yellow;' : null}}>{r.status}</span>)
              {/if}
        </p>
        {#if r.timestamps.size > 1}
        <p>All event timestamps: {Array.from(r.timestamps).join(", ")}</p>
        {/if}
        {#if !r.clearances.length && !r.violations.length}
          <p>No clearances, no violations</p>
        {:else}
          <Accordion>
            {#if r.clearances.length}
              <AccordionItem header={r.clearances.length + ' clearance(s)'}>
                <ListGroup>
                {#each r.clearances as c}
                  <ListGroupItem>{c}</ListGroupItem>
                {/each}
                </ListGroup>
              </AccordionItem>
            {/if}
            {#if r.violations.length}
              <AccordionItem>
                <p class="m-0" slot="header" style={(r.violations.length) ? 'background-color: yellow;' : null}>{r.violations.length + ' violation(s)'}</p>
                <ListGroup>
                {#each r.violations as v}
                  <ListGroupItem>{v}</ListGroupItem>
                {/each}
                </ListGroup>
              </AccordionItem>
            {/if}
          </Accordion>
        {/if}
      </ListGroupItem>
    {/each}
    </ListGroup>
    {:catch error}
      <FetchError {error}/>
    {/await}

    <Toast
      class="me-1"
      style="z-index: 10000; position:fixed; bottom: 2vh; right: 2vh;"
      autohide
      isOpen={toast_msg}
      on:close={() => (toast_msg = null)}
    >
      <ToastHeader icon={toast_msg?.color}>{toast_msg?.title}</ToastHeader>
      <ToastBody>{toast_msg?.msg}</ToastBody>
    </Toast>
</CardBody>
</Card>
{/if}
