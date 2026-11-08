<?php

function test_do_airtable_fetch_returns_error() {
  set_wp_remote_response(new WP_Error('boom'));
  $got = do_airtable_fetch('tok', 'base', 'table');
  assert_equal($got, ['error' => 'Fetch error: boom'], 'WP_Error is converted to an error payload');

  $reqs = wp_remote_requests();
  assert_equal(count($reqs), 1, 'one remote request is made');
  assert_equal($reqs[0]['url'], 'https://api.airtable.com/v0/base/table', 'request URL is built from base and table');
  assert_equal($reqs[0]['args']['headers']['Authorization'], 'Bearer tok', 'bearer token header is sent');
}

function test_do_airtable_fetch_decodes_success_body() {
  $records = [['id' => 'rec1', 'fields' => ['Name' => 'Example']]];
  set_wp_remote_response(['body' => json_encode(['records' => $records]), 'response' => ['code' => 200]]);

  assert_equal(do_airtable_fetch('tok', 'base', 'table'), ['records' => $records], 'JSON response is decoded to an array');
}

function test_do_airtable_fetch_returns_null_for_invalid_json() {
  set_wp_remote_response(['body' => 'not-json', 'response' => ['code' => 200]]);

  assert_equal(do_airtable_fetch('tok', 'base', 'table'), null, 'invalid JSON produces null');
}
