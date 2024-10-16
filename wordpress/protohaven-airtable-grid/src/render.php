<?php
/**
 * @see https://github.com/WordPress/gutenberg/blob/trunk/docs/reference-guides/block-api/block-metadata.md#render
 */
?>

<div
	class="protohaven-airtable-grid"
	data-img-size="<?php echo($attributes['imgSize']); ?>"
	data-title-field="<?php echo($attributes['titleField']); ?>"
	data-subtitle-field="<?php echo($attributes['subtitleField']); ?>"
	data-img-field="<?php echo($attributes['imgField']); ?>"
	data-body-field="<?php echo($attributes['bodyField']); ?>"
	data-ref-field="<?php echo($attributes['refField']); ?>"
	data-ref-text="<?php echo($attributes['refText']); ?>">
	<script type="text/json"><?php
	$token = $attributes['token'];
	$base = $attributes['base'];
	$table = $attributes['table'];
	$CACHE_ID = "ph_airtable_grid_$base_$table";
	$result = wp_cache_get($CACHE_ID);
	if ( false === $result || $result[1] < (time() - (60*60*24)) ) {
		$response = wp_remote_get("https://api.airtable.com/v0/$base/$table", array(
			'headers' => array(
			"Authorization" => "Bearer $token",
			)));
		if (is_wp_error($response)) {
			echo "Error $response";
		} else {
			$result = array(wp_remote_retrieve_body($response), time());
			wp_cache_set($CACHE_ID, $result);
		}
	}
	echo $result[0];
	?></script>
</div>
