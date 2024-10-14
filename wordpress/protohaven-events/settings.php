<?php

$PH_OPTIONS_GROUP_ID = 'ph_events_api_settings';
$PH_NEON_TOKEN_OPTION_ID = 'ph_events_api_key';
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
	global $PH_NEON_TOKEN_OPTION_ID;
  echo "<input name='$PH_NEON_TOKEN_OPTION_ID' type='text' value='" . esc_attr(get_option($PH_NEON_TOKEN_OPTION_ID)) . "' />";
}

function ph_events_validate_options( $input ) {
  return $input; // Passthrough
}

function ph_events_register_settings() {
	global $PH_SETTINGS_SLUG;
	global $PH_OPTIONS_GROUP_ID;
	global $PH_NEON_TOKEN_OPTION_ID;

  register_setting(
			$PH_OPTIONS_GROUP_ID, // option group
			$PH_NEON_TOKEN_OPTION_ID // option name
			// args[], previously 'ph_events_validate_options'
	);

  add_settings_section(
		$PH_OPTIONS_GROUP_ID, // settings section id
		'Neon API Settings', // title
		'ph_events_render_settings_section', // callback
		$PH_SETTINGS_SLUG // settings page
	);

	add_settings_field(
		$PH_NEON_TOKEN_OPTION_ID, // settings field id
		'Neon CRM user token', // title
		'ph_events_render_api_key_settings_field', // callback
		$PH_SETTINGS_SLUG, // settings page
		$PH_OPTIONS_GROUP_ID// section
	);
}
add_action( 'admin_init', 'ph_events_register_settings' );


?>
