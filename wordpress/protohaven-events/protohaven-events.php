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

$PH_OPTIONS_GROUP_ID = 'ph_events_api_settings';
$PH_PROTOHAVEN_API_URL_OPTION_ID = 'ph_events_protohaven_api_url';
$PH_SETTINGS_SLUG = 'ph-events-custom-settings-page';

function ph_events_register_custom_settings_page() {
	global $PH_SETTINGS_SLUG;
	add_options_page(
		'Protohaven Events Settings', // page title
		'Protohaven Events', // menu title
		'manage_options', // capability
		$PH_SETTINGS_SLUG, // menu slug
		'ph_events_render_custom_settings_page', //callback
		0 // position in menu list
	);
}
add_action( 'admin_menu', 'ph_events_register_custom_settings_page' );

function ph_events_render_custom_settings_page() {
	global $PH_OPTIONS_GROUP_ID;
	global $PH_SETTINGS_SLUG;
    ?>
    <h2>Protohaven Neon CRM Events Settings</h2>
    <form action="options.php" method="post">
        <?php settings_fields($PH_OPTIONS_GROUP_ID); ?>
        <?php do_settings_sections( $PH_SETTINGS_SLUG ); ?>
				<?php submit_button(); ?>
    </form>
    <?php
}

function ph_events_render_settings_section(){
	echo '<p>Settings for Neon CRM events integration. See <a href="https://github.com/protohaven/protohaven_api" target="_blank">github.com/protohaven/protohaven_api</a> for details.</p>';
}

function ph_events_render_api_key_settings_field() {
	global $PH_OPTIONS_GROUP_ID;
	global $PH_PROTOHAVEN_API_URL_OPTION_ID;
  echo "<input name='$PH_PROTOHAVEN_API_URL_OPTION_ID' type='text' value='" . esc_attr(get_option($PH_PROTOHAVEN_API_URL_OPTION_ID)) . "' />";
}

function ph_events_validate_options( $input ) {
  return $input; // Passthrough
}

function ph_events_register_settings() {
	global $PH_SETTINGS_SLUG;
	global $PH_OPTIONS_GROUP_ID;
	global $PH_PROTOHAVEN_API_URL_OPTION_ID;

  register_setting(
			$PH_OPTIONS_GROUP_ID, // option group
			$PH_PROTOHAVEN_API_URL_OPTION_ID // option name
			// args[], previously 'ph_events_validate_options'
	);

  add_settings_section(
		$PH_OPTIONS_GROUP_ID, // settings section id
		'Neon API Settings', // title
		'ph_events_render_settings_section', // callback
		$PH_SETTINGS_SLUG // settings page
	);

	add_settings_field(
		$PH_PROTOHAVEN_API_URL_OPTION_ID, // settings field id
		'protohaven_api server base url (e.g. http://protohaven_api:5000/', // title
		'ph_events_render_api_key_settings_field', // callback
		$PH_SETTINGS_SLUG, // settings page
		$PH_OPTIONS_GROUP_ID// section
	);
}
add_action( 'admin_init', 'ph_events_register_settings' );

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
            'callback' => 'ph_neon_event_tickets_cached',
            'permission_callback' => '__return_true'
        )
    );
}

function ph_neon_events() {
	global $PH_PROTOHAVEN_API_URL_OPTION_ID;
	$baseurl = get_option($PH_PROTOHAVEN_API_URL_OPTION_ID);
	$url = $baseurl."/events/upcoming";
	$response = wp_remote_get($url);
	if (is_wp_error($response)) {
		return "Error: " . $response->get_error_message();
	}
	// Wish we didn't have to do this decode step just to encode it again...
	return json_decode(wp_remote_retrieve_body($response), true);
}

function ph_neon_event_tickets($evt_id) {
	global $PH_PROTOHAVEN_API_URL_OPTION_ID;
	$baseurl = get_option($PH_PROTOHAVEN_API_URL_OPTION_ID);
	$url = $baseurl."/events/attendees?id=$evt_id";
	$response = wp_remote_get($url);
	if (is_wp_error($response)) {
		return "Error: " . $response->get_error_message();
	}
	// Wish we didn't have to do this decode step just to encode it again...
	return json_decode(wp_remote_retrieve_body($response), true);
}

function ph_neon_event_tickets_cached() {
	$evt_id = $_GET['evt_id'];
	$CACHE_ID = "ph_neon_event_tickets_$evt_id";
	$result = wp_cache_get($CACHE_ID);
	// Here we cache at 30 mins since ticket information is volatile.
	if ( false === $result || $result[1] < (time() - (30*60)) ) {
		$result = array(ph_neon_event_tickets($evt_id), time());
		if ($result[0] == 'Error') {
			return $result[0];
		}
		wp_cache_set($CACHE_ID, $result);
		$result = array("data" => $result[0], "cached" => false);
	} else {
		$result = array("data" => $result[0], "cached" => true);
	}
	return $result;
}
