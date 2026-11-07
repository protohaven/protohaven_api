<?php
/**
 * Plugin Name:       Protohaven Class Ticker
 * Description: 			A simple ticker showing upcoming Eventbrite classes at Protohaven - see https://github.com/protohaven/protohaven_api/
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


$PH_PROTOHAVEN_API_URL_OPTION_ID = 'ph_events_protohaven_api_url';

function ph_eventbrite_sample_events() {
	global $PH_PROTOHAVEN_API_URL_OPTION_ID;
	$baseurl = get_option($PH_PROTOHAVEN_API_URL_OPTION_ID);
	$url = $baseurl . "/event_ticker";
	$response = wp_remote_get($url);
	if (is_wp_error($response)) {
		error_log('protohaven-class-ticker: Error fetching ' . $url . ': ' . $response->get_error_message());
		return array();
	}
	$result = json_decode(wp_remote_retrieve_body($response), true);
	if (!is_array($result)) {
		error_log('protohaven-class-ticker: Invalid result on fetch to ' . $url);
		return array();
	}
	return $result;
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
