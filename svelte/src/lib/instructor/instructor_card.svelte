<script type="typescript" lang="ts">
import {
  Card, CardHeader, CardTitle, CardSubtitle, CardBody, CardFooter,
  Button, Badge, Modal, ModalHeader, ModalBody, ModalFooter, Input, FormGroup, Label, Row, Col
} from '@sveltestrap/sveltestrap';
import type { Instructor } from './types';

export let instructor: Instructor;
export let isCurrentUser: boolean;
export let isEducationLead: boolean;
export let onDisenroll: (inst: Instructor) => void;
export let modalOpen: boolean;
export let onToggleModal: () => void;

let editing = false;
let editedInstructor: Instructor = {...instructor};

function saveChanges() {
  // For now, we don't have instructor-specific fields to edit
  // This can be expanded later if needed
  editing = false;
}

function cancelEdit() {
  editedInstructor = {...instructor};
  editing = false;
}
</script>

<Card class="my-2">
  <CardHeader>
    <CardTitle>
      {instructor.name}
      {#if isCurrentUser}
        <Badge color="info" class="ms-2">You</Badge>
      {/if}
    </CardTitle>
    <CardSubtitle>{instructor.email}</CardSubtitle>
  </CardHeader>
  <CardBody>
    {#if instructor.volunteer_picture}
      <img src={instructor.volunteer_picture} alt={`${instructor.name} profile`} class="img-fluid rounded mb-3" style="max-height: 150px;" />
    {/if}

    {#if instructor.volunteer_bio}
      <p>{instructor.volunteer_bio}</p>
    {/if}

    <div class="d-flex flex-wrap gap-1">
      {#each instructor.clearances as clearance}
        <Badge color="secondary">{clearance}</Badge>
      {/each}
    </div>

    {#if instructor.clearances.length > 0}
      <Button color="link" size="sm" on:click={onToggleModal} class="mt-2">
        View all clearances ({instructor.clearances.length})
      </Button>
    {/if}
  </CardBody>

  {#if isEducationLead && !isCurrentUser}
    <CardFooter class="d-flex justify-content-end">
      <Button color="danger" size="sm" on:click={() => onDisenroll(instructor)}>
        Disenroll
      </Button>
    </CardFooter>
  {/if}
</Card>

<Modal isOpen={modalOpen} toggle={onToggleModal}>
  <ModalHeader toggle={onToggleModal}>Clearances for {instructor.name}</ModalHeader>
  <ModalBody>
    <ul>
      {#each instructor.clearances as clearance}
        <li>{clearance}</li>
      {/each}
    </ul>
  </ModalBody>
  <ModalFooter>
    <Button color="secondary" on:click={onToggleModal}>Close</Button>
  </ModalFooter>
</Modal>
