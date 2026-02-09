<script type="typescript" lang="ts">
  import { Card, CardHeader, CardTitle, CardBody, Container, Row, Col, Button, Modal } from '@sveltestrap/sveltestrap';
  import EditCell from './editable_td.svelte';
  import type { DisplayTech } from './types';

  export let tech: DisplayTech;
  export let isCurrentUser: boolean = false;
  export let isTechLead: boolean = false;
  export let onUpdate: (tech: DisplayTech) => void;
  export let onDisenroll: (tech: DisplayTech) => void;
  export let modalOpen: boolean = false;
  export let onToggleModal: () => void;
</script>

<Card class="my-2">
  <CardHeader>
    <div class="d-flex justify-content-between align-items-center">
      <CardTitle>{tech.name} ({tech.email})</CardTitle>
      {#if isTechLead && !isCurrentUser}
        <Button
          color="danger"
          size="sm"
          on:click={() => onDisenroll(tech)}
          title="Disenroll {tech.name}"
          aria-label="Disenroll {tech.name}"
        >
          Disenroll
        </Button>
      {/if}
    </div>
  </CardHeader>
  <CardBody>
    <Container style="max-width: none;">
      <Row cols={{ xxl: 2, xl: 2, l: 2, md: 2, sm: 1, xs: 1}}>
        <Col>
          <Row cols={{ xxl: 2, xl: 2, l: 2, md: 1, sm: 1, xs: 1}}>
            {#if tech.volunteer_bio}
              <img
                src={tech.volunteer_picture}
                style="max-width: 200px;"
                alt="Profile picture of {tech.name}"
              />
              <div>
                <strong>Bio</strong>
                <div>{tech.volunteer_bio}</div>
              </div>
            {:else if isCurrentUser}
              <a href="https://protohaven.org/mugshot" target="_blank">Submit your photo and bio!</a>
            {/if}
          </Row>
        </Col>
        <Col>
          <EditCell
            title="Shift"
            enabled={isTechLead}
            on_change={() => onUpdate(tech)}
            bind:value={tech.shop_tech_shift}
          />
          <EditCell
            title="First Day"
            enabled={isTechLead}
            on_change={() => onUpdate(tech)}
            bind:value={tech.shop_tech_first_day}
          />
          <EditCell
            title="Last Day"
            enabled={isTechLead}
            on_change={() => onUpdate(tech)}
            bind:value={tech.shop_tech_last_day}
          />
          <EditCell
            title="Area Lead"
            enabled={isTechLead}
            on_change={() => onUpdate(tech)}
            bind:value={tech.area_lead}
          />
          <EditCell
            title="Interest"
            enabled={true}
            on_change={() => onUpdate(tech)}
            bind:value={tech.interest}
          />
          <EditCell
            title="Expertise"
            enabled={true}
            on_change={() => onUpdate(tech)}
            bind:value={tech.expertise}
          />
          <Col>
            <Button
              outline
              on:click={onToggleModal}
              aria-label="View {tech.clearances.length} clearance(s) for {tech.name}"
            >
              {tech.clearances.length} Clearance(s)
            </Button>
          </Col>
        </Col>
      </Row>
    </Container>
  </CardBody>
</Card>

<Modal
  body
  header="Clearances"
  isOpen={modalOpen}
  toggle={onToggleModal}
  aria-labelledby="clearances-modal-title"
>
  {#each tech.clearances as c}
    <div>{c}</div>
  {/each}

  {#if isTechLead}
    <div class="my-3">
      <a
        href="https://docs.google.com/forms/d/e/1FAIpQLScX3HbZJ1-Fm_XPufidvleu6iLWvMCASZ4rc8rPYcwu_G33gg/viewform"
        target="_blank"
      >
        Submit additional clearances
      </a>
    </div>
  {/if}
</Modal>
