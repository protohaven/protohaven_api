<?php
/**
 * @see https://github.com/WordPress/gutenberg/blob/trunk/docs/reference-guides/block-api/block-metadata.md#render
 */
?>
<div
	id="protohaven-class-ticker"
	data-max-classes-shown="<?php echo($attributes['maxClassesShown']); ?>">
	<script type="text/json"><?php
	$CACHE_ID = "ph_neon_sample_events";
	$result = wp_cache_get($CACHE_ID);
	if ( false === $result || $result[1] < (time() - 3600) ) {
		$result = array(json_encode(ph_neon_sample_events()), time());
		wp_cache_set($CACHE_ID, $result );
	}
	echo $result[0];
	?></script>
</div>
