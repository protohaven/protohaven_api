<?php

function test_ph_events_get_events_returns_empty_on_error() {
  $_GET = [];
  set_wp_option('ph_events_protohaven_api_url', 'http://api.test');
  set_wp_remote_response(new WP_Error('boom'));

  assert_equal(ph_events_get_events(), ['events' => []], 'WP_Error response produces an empty events payload');

  $reqs = wp_remote_requests();
  assert_equal($reqs[0]['url'], 'http://api.test/events/upcoming', 'upcoming events URL is fetched');
  assert_equal($reqs[0]['args']['timeout'], 10, 'events request uses a 10 second timeout');
}

function test_ph_events_get_events_returns_empty_on_invalid_data() {
  $_GET = [];
  set_wp_option('ph_events_protohaven_api_url', 'http://api.test');
  set_wp_remote_response(['body' => 'not-json', 'response' => ['code' => 200]]);

  assert_equal(ph_events_get_events(), ['events' => []], 'invalid JSON produces an empty events payload');
}

function test_ph_events_get_events_returns_decoded_events() {
  $_GET = [];
  set_wp_option('ph_events_protohaven_api_url', 'http://api.test');
  $result = ['events' => [['name' => 'Wood 101']]];
  set_wp_remote_response(['body' => json_encode($result), 'response' => ['code' => 200]]);

  assert_equal(ph_events_get_events(), $result, 'valid events payload is returned');
}

function test_ph_events_get_event_tickets_returns_empty_on_error() {
  $_GET = [];
  set_wp_option('ph_events_protohaven_api_url', 'http://api.test');
  set_wp_remote_response(new WP_Error('boom'));

  assert_equal(ph_events_get_event_tickets('evt123'), [], 'WP_Error response produces an empty ticket list');

  $reqs = wp_remote_requests();
  assert_equal($reqs[0]['url'], 'http://api.test/events/tickets?id=evt123', 'ticket URL includes the event id');
  assert_equal($reqs[0]['args']['timeout'], 10, 'ticket request uses a 10 second timeout');
}

function test_ph_events_get_event_tickets_returns_decoded_tickets() {
  $_GET = [];
  set_wp_option('ph_events_protohaven_api_url', 'http://api.test');
  $tickets = [['name' => 'Single Registration', 'sold' => 1]];
  set_wp_remote_response(['body' => json_encode($tickets), 'response' => ['code' => 200]]);

  assert_equal(ph_events_get_event_tickets('evt123'), $tickets, 'valid ticket JSON is returned');
}

function test_ph_events_get_event_tickets_cached_returns_fresh_ticket_data() {
  $_GET = ['evt_id' => 'evt123'];
  set_wp_option('ph_events_protohaven_api_url', 'http://api.test');
  $tickets = [['name' => 'Single Registration', 'sold' => 2]];
  set_wp_remote_response(['body' => json_encode($tickets), 'response' => ['code' => 200]]);

  assert_equal(
    ph_events_get_event_tickets_cached(),
    ['data' => $tickets, 'cached' => false],
    'cache miss fetches and returns fresh ticket data'
  );

  $cached = wp_cache_get('ph_eventbrite_event_tickets_evt123');
  assert_equal($cached[0], $tickets, 'fetched tickets are stored in the cache');
  assert_true(abs($cached[1] - time()) <= 1, 'cache timestamp is current');
}

function test_ph_events_get_event_tickets_cached_returns_cached_ticket_data() {
  $_GET = ['evt_id' => 'evt123'];
  $tickets = [['name' => 'Single Registration', 'sold' => 2]];
  set_wp_cache('ph_eventbrite_event_tickets_evt123', [$tickets, time()]);

  assert_equal(
    ph_events_get_event_tickets_cached(),
    ['data' => $tickets, 'cached' => true],
    'cache hit returns cached ticket data'
  );
  assert_equal(count(wp_remote_requests()), 0, 'cache hit does not make a remote request');
}

function test_ph_events_validate_options_passthrough() {
  assert_equal(ph_events_validate_options(['a' => 1]), ['a' => 1], 'validation is a passthrough');
}
