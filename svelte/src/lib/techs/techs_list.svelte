<script type="typescript">
import { onMount } from 'svelte';
import {
  Table, Dropdown, DropdownToggle, DropdownItem, DropdownMenu, Button, Row, Container, Col, Card,
  CardHeader, Badge, CardTitle, Modal, CardSubtitle, CardText, Icon, Tooltip, CardFooter, CardBody,
  Input, Spinner, FormGroup, Navbar, NavbarBrand, Nav, NavItem, Toast, ToastBody, ToastHeader,
  ListGroup, ListGroupItem
} from '@sveltestrap/sveltestrap';
import { get, post } from '$lib/api.ts';
import type { Tech, DisplayTech, SearchResult, ToastMessage, SortType, TechListData } from './types';
import FetchError from '../fetch_error.svelte';
import TechCard from './TechCard.svelte';

// Utility functions
function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null;

  return (...args: Parameters<T>) => {
    if (timeout) {
      clearTimeout(timeout);
    }
    timeout = setTimeout(() => {
      func(...args);
    }, wait);
  };
}

function handleApiError(error: any, context: string): ToastMessage {
  console.error(`${context}:`, error);
  return {
    color: 'danger',
    msg: `Failed to ${context}. Please try again.`,
    title: 'Error'
  };
}

// Component props
export let visible: boolean;
export let user: { email: string };

// State
let loaded = false;
let promise: Promise<TechListData> = Promise.resolve({ techs: [], tech_lead: false });

let new_tech: { neon_id: string | null; name: string; email: string } = { neon_id: null, name: "", email: "" };
let toast_msg: ToastMessage | null = null;
let search_term = "";
let search_results: SearchResult[] = [];
let searching = false;
let search_promise: Promise<SearchResult[]> = Promise.resolve([]);
let show_create_account = false;
let enrolling = false;

let techs: DisplayTech[] = [];
let techs_sorted: DisplayTech[] = [];
let user_data: DisplayTech | null = null;
let sort_type: SortType = "clearances_desc";

// Reactive sort
$: {
  if (sort_type === "clearances_desc") {
    techs_sorted = [...techs].sort((a, b) => b.clearances.length - a.clearances.length);
  } else if (sort_type === "clearances_asc") {
    techs_sorted = [...techs].sort((a, b) => a.clearances.length - b.clearances.length);
  } else if (sort_type === "name") {
    techs_sorted = [...techs].sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()));
  }
}

// Debounced search function
const debouncedSearch = debounce(() => {
  if (!search_term.trim()) {
    search_results = [];
    return;
  }

  searching = true;
  search_promise = post(`/neon_lookup?search=${search_term}`)
    .then((results: SearchResult[]) => {
      search_results = results;
    })
    .catch((err) => {
      console.error("Search failed:", err);
      search_results = [];
      toast_msg = handleApiError(err, 'search Neon accounts');
    })
    .finally(() => {
      searching = false;
    });
}, 300);

// Functions
function refresh() {
  promise = get("/techs/list")
    .then((data: TechListData) => {
      loaded = true;
      techs = data.techs.map((t: Tech) => {
        const displayTech: DisplayTech = {
          ...t,
          shop_tech_shift: Array.isArray(t.shop_tech_shift) ? t.shop_tech_shift.join(' ') : t.shop_tech_shift
        };
        if (t.email.trim().toLowerCase() === user.email.trim().toLowerCase()) {
          user_data = displayTech;
        }
        return displayTech;
      });
      return data;
    })
    .catch((error) => {
      toast_msg = handleApiError(error, 'load techs');
      throw error;
    });
}

function search_neon_accounts() {
  debouncedSearch();
}

// Reactive visibility
$: {
  if (visible && !loaded) {
    refresh();
  }
}

// Reactive search term
$: {
  if (search_term) {
    search_neon_accounts();
  } else {
    search_results = [];
    new_tech.neon_id = null;
    new_tech.name = "";
    new_tech.email = "";
  }
}

function is_enrolled(neon_id: string | null): boolean {
  if (!neon_id) return false;
  for (let t of techs || []) {
    if (t.neon_id == neon_id) {
      return true;
    }
  }
  return false;
}

function update_tech(t: DisplayTech) {
  // Convert shop_tech_shift back to array for API
  const apiTech = {
    ...t,
    shop_tech_shift: t.shop_tech_shift ? t.shop_tech_shift.split(' ').filter(Boolean) : []
  };

  post("/techs/update", apiTech)
    .then(() => {
      toast_msg = {
        color: 'success',
        msg: `${t.name} updated`,
        title: 'Edit Success'
      };
    })
    .catch((error) => {
      toast_msg = handleApiError(error, 'update tech');
    });
}

function set_enrollment(enroll: boolean) {
  // If we're trying to enroll but haven't selected a Neon account from search,
  // and we're not in create account mode, we can't proceed
  if (enroll && !new_tech.neon_id && !show_create_account) {
    toast_msg = {
      color: 'warning',
      msg: 'Please select a Neon account from search results or create a new account',
      title: 'No account selected'
    };
    return;
  }

  enrolling = true;

  let payload = {
    ...new_tech,
    enroll
  };

  // If we're creating a new account, include name and email
  if (show_create_account && enroll) {
    payload['create_account'] = true;
  }

  post("/techs/enroll", payload)
    .then(() => {
      toast_msg = {
        color: 'success',
        msg: `${payload.name} successfully ${enroll ? 'enrolled' : 'disenrolled'}.`,
        title: 'Enrollment changed'
      };

      // Reset form
      search_term = "";
      search_results = [];
      if (show_create_account) {
        show_create_account = false;
        new_tech.name = "";
        new_tech.email = "";
      }
      new_tech.neon_id = null;

      // Refresh the list
      refresh();
    })
    .catch((error) => {
      toast_msg = handleApiError(error, 'change enrollment');
    })
    .finally(() => {
      enrolling = false;
    });
}

function disenroll_tech(t: DisplayTech) {
  if (!confirm(`Are you sure you want to disenroll ${t.name} as a shop tech?`)) {
    return;
  }

  enrolling = true;
  post("/techs/enroll", { neon_id: t.neon_id, enroll: false })
    .then(() => {
      toast_msg = {
        color: 'success',
        msg: `${t.name} successfully disenrolled.`,
        title: 'Disenrollment successful'
      };
      // Refresh the list
      refresh();
    })
    .catch((error) => {
      toast_msg = handleApiError(error, 'disenroll tech');
    })
    .finally(() => {
      enrolling = false;
    });
}

let modal_open: string | null = null;
function clearance_click(id: string) {
  if (modal_open !== id) {
    modal_open = id;
  } else {
    modal_open = null;
  }
}
</script>

{#if visible}
  <Card>
    <CardHeader>
      <CardTitle>Tech Roster</CardTitle>
      <CardSubtitle>Current info on all techs</CardSubtitle>
    </CardHeader>
    <CardBody>
      {#await promise}
        <Spinner aria-label="Loading tech roster..."/>
      {:then p}
        {#if user_data}
          <TechCard
            tech={user_data}
            isCurrentUser={true}
            isTechLead={p.tech_lead}
            onUpdate={update_tech}
            onDisenroll={disenroll_tech}
            modalOpen={modal_open === user_data.email}
            onToggleModal={() => clearance_click(user_data.email)}
          />
          <hr>
        {/if}

        <div class="d-flex">
          {#if enrolling}
            <Spinner size="sm" class="me-2" aria-label="Processing enrollment..."/>
          {/if}
          <Dropdown>
            <DropdownToggle color="light" caret aria-label="Sort options">
              Sort
            </DropdownToggle>
            <DropdownMenu>
              <DropdownItem on:click={() => sort_type = "clearances_asc"}>Least Clearances</DropdownItem>
              <DropdownItem on:click={() => sort_type = "clearances_desc"}>Most Clearances</DropdownItem>
              <DropdownItem on:click={() => sort_type = "name"}>By Name</DropdownItem>
            </DropdownMenu>
          </Dropdown>

          {#if p.tech_lead}
            {#if !show_create_account}
              <div class="mx-1 position-relative">
                <div class="d-flex align-items-center">
                  <Input
                    class="me-1"
                    text
                    bind:value={search_term}
                    placeholder="Search by name or email"
                    disabled={enrolling}
                    aria-label="Search Neon accounts by name or email"
                    aria-describedby="search-help"
                  />
                  {#if searching}
                    <Spinner size="sm" class="me-1" aria-label="Searching..."/>
                  {/if}
                  <Button
                    color="secondary"
                    size="sm"
                    on:click={() => {
                      search_term = "";
                      search_results = [];
                      new_tech.neon_id = null;
                      new_tech.name = "";
                      new_tech.email = "";
                      show_create_account = true;
                    }}
                    disabled={enrolling}
                    aria-label="Create new account"
                  >
                    <Icon name="plus" class="me-1" /> New Account
                  </Button>
                </div>

                <div id="search-help" class="visually-hidden">
                  Search for Neon accounts by name or email. Results will appear below.
                </div>

                {#if search_results.length > 0}
                  <div
                    class="position-absolute bg-white border rounded shadow mt-1"
                    style="z-index: 1000; width: 100%; max-height: 300px; overflow-y: auto;"
                    role="listbox"
                    aria-label="Search results"
                    aria-expanded="true"
                  >
                    <ListGroup flush>
                      {#each search_results as result}
                        <ListGroupItem
                          tag="button"
                          action
                          on:click={() => {
                            new_tech.neon_id = result.neon_id;
                            new_tech.name = result.name;
                            new_tech.email = result.email;
                            search_term = "";
                            search_results = [];
                          }}
                          class="text-start"
                          role="option"
                          aria-selected={new_tech.neon_id === result.neon_id}
                        >
                          {result.name} ({result.email})
                        </ListGroupItem>
                      {/each}
                    </ListGroup>
                  </div>
                {/if}
              </div>
            {:else}
              <div class="mx-1 d-flex align-items-center">
                <Input
                  class="me-1"
                  text
                  bind:value={new_tech.name}
                  placeholder="Full name"
                  disabled={enrolling}
                  aria-label="Full name for new account"
                />
                <Input
                  class="me-1"
                  text
                  bind:value={new_tech.email}
                  placeholder="Email address"
                  disabled={enrolling}
                  aria-label="Email address for new account"
                />
                <Button
                  color="secondary"
                  size="sm"
                  on:click={() => {
                    show_create_account = false;
                    new_tech.name = "";
                    new_tech.email = "";
                    search_term = "";
                    search_results = [];
                  }}
                  disabled={enrolling}
                  aria-label="Cancel new account creation"
                >
                  Cancel
                </Button>
              </div>
            {/if}

            <Button
              class="mx-1"
              on:click={() => set_enrollment(true)}
              disabled={enrolling || is_enrolled(new_tech.neon_id) || !new_tech.name || !new_tech.email}
              aria-label={show_create_account ? "Create and enroll new account" : "Enroll selected account"}
            >
              {#if show_create_account}
                Create & Enroll
              {:else}
                Enroll
              {/if}
            </Button>
            <Button
              class="mx-1"
              on:click={() => set_enrollment(false)}
              disabled={enrolling || (new_tech.neon_id && !is_enrolled(new_tech.neon_id)) || !new_tech.neon_id}
              aria-label="Disenroll selected account"
            >
              Disenroll
            </Button>
          {/if}
        </div>

        <Toast
          class="me-1"
          style="z-index: 10000; position:fixed; bottom: 2vh; right: 2vh;"
          autohide
          isOpen={toast_msg}
          on:close={() => (toast_msg = null)}
          aria-live="polite"
          aria-atomic="true"
        >
          <ToastHeader icon={toast_msg.color}>{toast_msg.title}</ToastHeader>
          <ToastBody>{toast_msg.msg}</ToastBody>
        </Toast>

        {#each techs_sorted as t}
          {#if t.email !== user_data?.email}
            <TechCard
              tech={t}
              isCurrentUser={false}
              isTechLead={p.tech_lead}
              onUpdate={update_tech}
              onDisenroll={disenroll_tech}
              modalOpen={modal_open === t.email}
              onToggleModal={() => clearance_click(t.email)}
            />
          {/if}
        {/each}
      {:catch error}
        <FetchError {error}/>
      {/await}
    </CardBody>
  </Card>
{/if}
