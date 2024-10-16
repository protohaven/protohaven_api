<?php
/**
 * Plugin Name:       Protohaven Class Ticker
 * Description: 			A simple ticker showing upcoming classes at Protohaven - see https://github.com/protohaven/protohaven_api/
 * Requires at least: 6.6
 * Requires PHP:      7.2
 * Version:           0.1.0
 * Author: 						Scott Martin (smartin015@gmail.com)
 * License:           GPL-2.0-or-later
 * License URI:       https://www.gnu.org/licenses/gpl-2.0.html:
 * Text Domain:       protohaven-class-ticker
 *
 * @package CreateBlock
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Exit if accessed directly.
}


$PH_NEON_TOKEN_OPTION_ID = 'ph_events_api_key';

function ph_neon_sample_events() {
	global $PH_NEON_TOKEN_OPTION_ID;
	$token = get_option($PH_NEON_TOKEN_OPTION_ID);
	$url = "https://protohaven:$token@api.neoncrm.com/v2/events/search";
  $body = array(
      "searchFields" => array(
          array(
              "field" => "Event Start Date",
              "operator" => "GREATER_AND_EQUAL",
              "value" => date("Y-m-d"),
          ),
          array(
              "field" => "Event Start Date",
              "operator" => "LESS_AND_EQUAL",
              "value" => (new DateTime())->modify('+14 days')->format("Y-m-d"),
          ),
      ),
      "outputFields" => array(
          "Event ID",
          "Event Name",
          "Event Web Publish",
          "Event Web Register",
          "Event Registration Attendee Count",
          "Event Capacity",
          "Event Start Date",
          "Event Start Time",
			),
			"pagination" => array(
				"currentPage" => 0,
				"pageSize" => 50,
			),
	);
	$response = wp_remote_post($url, array(
		"headers" => array("Content-Type" => "application/json"),
		"body" => json_encode($body))
	);
	if (is_wp_error($response)) {
		return "Error";
	}
	$result = json_decode(wp_remote_retrieve_body($response), true);
	$sample_classes = array();
	foreach ($result['searchResults'] as $e) {
		if ($e['Event Web Publish'] != "Yes" or $e['Event Web Register'] != "Yes") {
			continue;
		}
		$capacity = intval($e['Event Capacity']);
		$numreg = intval($e['Event Registration Attendee Count']);
		if ($capacity <= $numreg) {
			continue;
		}
		if (empty($e['Event Start Date']) || empty($e['Event Start Time'])) {
			continue;
		}
		$d = new DateTime($e['Event Start Date'] . ' ' . $e['Event Start Time'], new DateTimeZone('America/New_York'));
		$d = $d->format('M j, gA');
		$sample_classes[] = [
			'url' => "https://protohaven.org/e/" . $e['Event ID'],
			'name' => $e['Event Name'],
			'date' => $d,
			'seats_left' => $capacity - $numreg,
		];
		if (count($sample_classes) >= 3) {
			break;
		}
	}
	return $sample_classes;
}

/**
 * Registers the block using the metadata loaded from the `block.json` file.
 * Behind the scenes, it registers also all assets so they can be enqueued
 * through the block editor in the corresponding context.
 *
 * @see https://developer.wordpress.org/reference/functions/register_block_type/
 */
function create_block_protohaven_class_ticker_block_init() {
	register_block_type( __DIR__ . '/build' );
}
add_action( 'init', 'create_block_protohaven_class_ticker_block_init' );
