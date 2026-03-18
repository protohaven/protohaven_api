<script type="typescript" lang="ts">
import { onMount } from 'svelte';
import {
  Alert,
  Table, Dropdown, DropdownToggle, DropdownItem, DropdownMenu, Button, Row, Container, Col, Card,
  CardHeader, Badge, CardTitle, Modal, CardSubtitle, CardText, Icon, Tooltip, CardFooter, CardBody,
  Input, Spinner, FormGroup, Navbar, NavbarBrand, Nav, NavItem, Toast, ToastBody, ToastHeader,
  ListGroup, ListGroupItem,
} from '@sveltestrap/sveltestrap';
import { get, post } from '$lib/api.ts';
import type { Instructor, DisplayInstructor, SearchResult, ToastMessage, SortType, InstructorListData, InstructorCapability } from './types';
import FetchError from '../fetch_error.svelte';
import InstructorCard from './instructor_card.svelte';

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
export let admin: boolean;
export let data: InstructorListData | null = null;
export let onEnrollmentChanged;

// State
let loaded = false;

let new_instructor: { neon_id: string | null; name: string; email: string } = { neon_id: null, name: "", email: "" };
let toast_msg: ToastMessage | null = null;
let search_term = "";
let search_results: SearchResult[] = [];
let searching = false;
let search_promise: Promise<SearchResult[]> = Promise.resolve([]);
let show_create_account = false;
let enrolling = false;

let capabilities: InstructorCapability[] = [];
let enrollment_map = {};
let without_capabilities = new Set();
let show_capabilities = false;

// Debounced search function
const debouncedSearch = debounce(() => {
  new_instructor = {neon_id: null, name: "", email: ""};
  if (!search_term.trim()) {
    search_results = [];
    return;
  }

  searching = true;
  search_promise = post(`/neon_lookup?search=${encodeURIComponent(search_term)}`)
    .then((results: SearchResult[]) => {
      search_results = results;
      search_results.push({name: "+ Create New", email: "Neon CRM"});
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
// Process data when it becomes available
$: {
  if (data && !loaded) {
    loaded = true;
    capabilities = data.capabilities || [];
    enrollment_map = data.enrollment_map || {};
    console.log(enrollment_map);

    const cap_neon_ids = new Set(capabilities.map((c) => c.neon_id));
    const enrolled_neon_ids = new Set(Object.keys(enrollment_map));
    without_capabilities = Array.from(enrolled_neon_ids.difference(cap_neon_ids));
  }
}

function search_neon_accounts() {
  debouncedSearch();
}

// Reactive search term
function on_search_term_edit(e) {
  console.log(e);
  if (search_term !== `${new_instructor.name} (${new_instructor.email})`) {
    search_neon_accounts();
  } else {
    search_results = [];
    new_instructor.neon_id = null;
    new_instructor.name = "";
    new_instructor.email = "";
  }
}

function is_enrolled(neon_id: string | null): boolean {
  return (neon_id && enrollment_map[neon_id]);
}

function set_enrollment(enroll: boolean) {
  // If we're trying to enroll but haven't selected a Neon account from search,
  // and we're not in create account mode, we can't proceed
  if (enroll && !new_instructor.neon_id && !show_create_account) {
    toast_msg = {
      color: 'warning',
      msg: 'Please select a Neon account from search results or create a new account',
      title: 'No account selected'
    };
    return;
  }

  enrolling = true;

  let payload = {
    ...new_instructor,
    enroll
  };

  // If we're creating a new account, include name and email
  if (show_create_account && enroll) {
    payload['create_account'] = true;
  }

  post("/instructor/enroll", payload)
    .then(() => {
      toast_msg = {
        color: 'success',
        msg: `${payload.name} successfully ${enroll ? 'enrolled' : 'disenrolled'} as instructor.`,
        title: 'Enrollment changed'
      };

      // Reset form
      search_term = "";
      search_results = [];
      if (show_create_account) {
        show_create_account = false;
        new_instructor.name = "";
        new_instructor.email = "";
      }
      new_instructor.neon_id = null;

      // Refresh the list
      onEnrollmentChanged();
    })
    .catch((error) => {
      toast_msg = handleApiError(error, 'change enrollment');
    })
    .finally(() => {
      enrolling = false;
    });
}

function disenroll_instructor(inst: Instructor) {
  if (!confirm(`Are you sure you want to disenroll ${inst.name} as an instructor?`)) {
    return;
  }

  enrolling = true;
  post("/instructor/enroll", { neon_id: inst.neon_id, enroll: false })
    .then(() => {
      toast_msg = {
        color: 'success',
        msg: `${inst.name} successfully disenrolled as instructor.`,
        title: 'Disenrollment successful'
      };
      // Refresh the list
      onEnrollmentChanged();
    })
    .catch((error) => {
      toast_msg = handleApiError(error, 'disenroll instructor');
    })
    .finally(() => {
      enrolling = false;
    });
}

</script>

{#if visible}
  <Card>
    <CardHeader>
      <CardTitle>Instructor Roster</CardTitle>
      <CardSubtitle>Current info on all instructors</CardSubtitle>
    </CardHeader>
    <CardBody>
        <div class="d-flex">
          {#if enrolling}
            <Spinner size="sm" class="me-2" aria-label="Processing enrollment..."/>
          {/if}

          {#if admin}
            {#if !show_create_account}
              <div class="mx-1 position-relative">
                <div class="d-flex align-items-center">
                  <div data-help="this div needed for on:keydown">
                  <Input
                    class="me-1"
                    type="text"
                    bind:value={search_term}
                    on:keydown={on_search_term_edit}
                    placeholder="Search by name or email"
                    disabled={enrolling}
                    aria-label="Search Neon accounts by name or email"
                    aria-describedby="search-help"
                  />
                  </div>
                  {#if searching}
                    <Spinner size="sm" class="me-1" aria-label="Searching..."/>
                  {/if}
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
                            if (result.name === "+ Create New") {
                              show_create_account=true;
                              search_results = [];
                              return;
                            }
                            new_instructor.neon_id = result.neon_id;
                            new_instructor.name = result.name;
                            new_instructor.email = result.email;
                            search_term = `${new_instructor.name} (${new_instructor.email})`; // For visibility
                            search_results = [];
                          }}
                          class="text-start"
                          role="option"
                          aria-selected={new_instructor.neon_id === result.neon_id}
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
                  type="text"
                  bind:value={new_instructor.name}
                  placeholder="Full name"
                  disabled={enrolling}
                  aria-label="Full name for new account"
                />
                <Input
                  class="me-1"
                  type="email"
                  bind:value={new_instructor.email}
                  placeholder="Email address"
                  disabled={enrolling}
                  aria-label="Email address for new account"
                />
                <Button
                  color="secondary"
                  size="sm"
                  on:click={() => {
                    show_create_account = false;
                    new_instructor.name = "";
                    new_instructor.email = "";
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
              size="sm"
              on:click={() => set_enrollment(true)}
              disabled={enrolling || is_enrolled(new_instructor.neon_id) || !new_instructor.name || !new_instructor.email}
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
              size="sm"
              on:click={() => set_enrollment(false)}
              disabled={enrolling || (new_instructor.neon_id && !is_enrolled(new_instructor.neon_id)) || !new_instructor.neon_id}
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
        {#if without_capabilities.length > 0}
        <Alert color="warning">The following people are enrolled as instructors in Neon CRM but they have no capabilities in airtable:
        <ul>
        {#each without_capabilities as nid }
          <li>
          <a href={"https://protohaven.app.neoncrm.com/admin/accounts/" + nid} target="_blank">{enrollment_map[nid]}</a>
          </li>
        {/each}
        </ul>
        <p>To enable class scheduling and reminders, they must also be added to <a href="https://airtable.com/applultHGJxHNg69H/tbltv8tpiCqUnLTp4/viwqTK2puFGyz0RhI">Instructor Capabilities</a>. If this is a mistake, disenroll them using the search box above.</p>
        </Alert>
        {/if}
        <h3>Capabilities</h3>
        <div class="my-3">
          <p>Instructor data is fetched from <a href="https://airtable.com/applultHGJxHNg69H/tbltv8tpiCqUnLTp4/viwqTK2puFGyz0RhI" target="_blank">Airtable</a>.
          Contact the Software Dev team via Discord if you need to make a change to anything listed here.</p>
        </div>

          <Table responsive striped hover>
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Enrolled</th>
                <th>Active</th>
                <th>Paperwork</th>
                <th>Classes</th>
                <th>Actions</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
            {#each capabilities as inst}
              <tr>
                <td>
                  {inst.name}
                </td>
                <td>{inst.email}</td>
            <td>{is_enrolled(inst.neon_id) ? "Yes" : "No"}</td>
                <td>
                  {#if inst.active}
                    <Badge color="success">Active</Badge>
                  {:else}
                    <Badge color="secondary">Inactive</Badge>
                  {/if}
                </td>
                <td>
                  {#if inst.paperwork_complete}
                    <Badge color="success">Complete</Badge>
                  {:else}
                    <Badge color="warning">Incomplete</Badge>
                  {/if}
                </td>
                <td>
                  {#if Object.keys(inst.classes).length > 0}
                    <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                      {#each Object.entries(inst.classes) as [id, name]}
                        <Badge color="primary" pill>{name}</Badge>
                      {/each}
                    </div>
                  {:else}
                    —
                  {/if}
                </td>
                <td>
                  <a href={"/instructor?email=" + encodeURIComponent(inst.email)} target="_blank" class="btn btn-sm btn-primary">
                    View Page
                  </a>
                </td><td>
                  <a href={"https://protohaven.app.neoncrm.com/admin/accounts/" + inst.neon_id} class="btn btn-sm btn-primary">Neon CRM</a>
                </td>
              </tr>
            {/each}
            </tbody>
          </Table>

          </CardBody>
      </Card>
{/if}
