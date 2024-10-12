<?php
/**
 * Plugin Name:       Protohaven Events
 * Description: 			Load and render Neon CRM events - see https://github.com/protohaven/protohaven_api/
 * Requires at least: 6.6
 * Requires PHP:      7.2
 * Version:           0.1.0
 * Author: 						Scott Martin (smartin015@gmail.com)
 * License:           GPL-2.0-or-later
 * License URI:       https://www.gnu.org/licenses/gpl-2.0.html:
 * Text Domain:       protohaven-events
 *
 * @package CreateBlock
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Exit if accessed directly.
}

/**
 * Registers the block using the metadata loaded from the `block.json` file.
 * Behind the scenes, it registers also all assets so they can be enqueued
 * through the block editor in the corresponding context.
 *
 * @see https://developer.wordpress.org/reference/functions/register_block_type/
 */
function create_block_protohaven_events_block_init() {
	register_block_type( __DIR__ . '/build' );
}
add_action( 'init', 'create_block_protohaven_events_block_init' );


add_action( 'rest_api_init', 'ph_neon_register_routes' );
function ph_neon_register_routes() {
	register_rest_route(
	'protohaven-events-plugin-api/v1',
        '/events/',
        array(
            'methods'  => 'GET',
            'callback' => 'ph_neon_events',
            'permission_callback' => '__return_true'
        )
    );
	register_rest_route(
	'protohaven-events-plugin-api/v1',
        '/event_tickets/',
        array(
            'methods'  => 'GET',
            'callback' => 'ph_neon_event_tickets',
            'permission_callback' => '__return_true'
        )
    );
}

function ph_neon_events() {
	$token = "d819576d3cbb9e4fabee8dd6e2a921e4";
	$url = "https://protohaven:$token@api.neoncrm.com/v2/events";
	$query_params = $_GET;
	if (!empty($query_params)) {
	    $url .= '?' . http_build_query($query_params);
	}
	$response = wp_remote_get($url);
	if (is_wp_error($response)) {
		return "Error";
	}
	// Wish we didn't have to do this decode step just to encode it again...
	return json_decode(wp_remote_retrieve_body($response), true);
}

function ph_neon_event_tickets() {
	$token = "d819576d3cbb9e4fabee8dd6e2a921e4";
	$neon_id = $_GET['neon_id'];
	$url = "https://protohaven:$token@api.neoncrm.com/v2/events/$neon_id/tickets";
	$query_params = $_GET;
	if (!empty($query_params)) {
	    $url .= '?' . http_build_query($query_params);
	}
	$response = wp_remote_get($url);
	if (is_wp_error($response)) {
		return "Error";
	}
	// Wish we didn't have to do this decode step just to encode it again...
	return json_decode(wp_remote_retrieve_body($response), true);
}
