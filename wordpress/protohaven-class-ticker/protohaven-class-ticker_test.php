<?php

function test_ph_eventbrite_sample_events_returns_empty_on_error() {
  set_wp_option('ph_events_protohaven_api_url', 'http://api.test');
  set_wp_remote_response(new WP_Error('boom'));

  assert_equal(ph_eventbrite_sample_events(), [], 'WP_Error response produces an empty list');

  $reqs = wp_remote_requests();
  assert_equal(count($reqs), 1, 'one remote request is made');
  assert_equal($reqs[0]['url'], 'http://api.test/event_ticker', 'event ticker URL is fetched');
}

function test_ph_eventbrite_sample_events_returns_empty_on_invalid_json() {
  set_wp_option('ph_events_protohaven_api_url', 'http://api.test');
  set_wp_remote_response(['body' => 'not-json', 'response' => ['code' => 200]]);

  assert_equal(ph_eventbrite_sample_events(), [], 'invalid JSON produces an empty list');
}

function test_ph_eventbrite_sample_events_returns_decoded_events() {
  set_wp_option('ph_events_protohaven_api_url', 'http://api.test');
  $events = [['name' => 'Wood 101', 'date' => 'Oct 1']];
  set_wp_remote_response(['body' => json_encode($events), 'response' => ['code' => 200]]);

  assert_equal(ph_eventbrite_sample_events(), $events, 'valid JSON response is returned');
}
