<?php
/**
 * Plugin Name:       Protohaven Airtable Grid
 * Description: 			Load and render Airtable data without an iframe - see https://github.com/protohaven/protohaven_api/
 * Requires at least: 6.6
 * Requires PHP:      7.2
 * Version:           0.1.0
 * Author: 						Scott Martin (smartin015@gmail.com)
 * License:           GPL-2.0-or-later
 * License URI:       https://www.gnu.org/licenses/gpl-2.0.html:
 * Text Domain:       protohaven-airtable-grid
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
function create_block_protohaven_airtable_grid_block_init() {
	register_block_type( __DIR__ . '/build' );
}
add_action( 'init', 'create_block_protohaven_airtable_grid_block_init' );
