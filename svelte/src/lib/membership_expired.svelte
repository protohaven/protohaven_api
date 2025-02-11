<script lang="ts">
  import { Alert, Button, Row, Col } from '@sveltestrap/sveltestrap';
  export let on_close;
  export let name;
</script>

<Alert color="danger" fade={false} open={true}>
  <Row class="text-center justify-content-center">
    <h1>{name}, please see a tech on duty.</h1>
    <h3>Your membership is not listed as active.</h3>
    <p>See the whiteboard by the front desk for current on-duty techs.</p>
    <p><em>Note: it may take up to 24 hours for changes in your membership to be processed.</em></p>
  </Row>

  <Row class="justify-content-center">
    <Col sm={{size: 'auto'}} class="my-3">
    <Button color="danger" on:click={on_close}>Done</Button>
    </Col>
  </Row>
</Alert>
