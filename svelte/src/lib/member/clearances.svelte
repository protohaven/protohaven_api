<script type="typescript">
import {Accordion, AccordionItem, Badge, Card, Spinner, ListGroup, ListGroupItem, CardTitle, CardSubtitle, CardHeader, CardBody, CardFooter, Button, Input, Navbar, NavbarBrand, Nav, NavItem, NavLink } from '@sveltestrap/sveltestrap';

export let clearances;
export let visible;

</script>


{#if visible}
<Card class="my-3">
<CardHeader>
<CardTitle>Clearances</CardTitle>
</CardHeader>
<CardBody>
  <p><strong>Clearances</strong> grant access to use equipment without instructor supervision. For more details, see our <a href="https://wiki.protohaven.org/books/members-handbook/page/getting-cleared-on-tools" target="_blank">Member Guide</a>.</p>
  {#if clearances.length == 0}
    <p>Looks like you don't have any equipment clearances yet.</p>
    <p>Why not <a href="https://protohaven.org/classes" target="_blank">take a class?</a></p>
  {:else}
  <h4>Your Clearances:</h4>
  {#each clearances as c}
    <Badge color="light">{c}</Badge>
  {/each}
  {/if}
</CardBody>
</Card>
{/if}
