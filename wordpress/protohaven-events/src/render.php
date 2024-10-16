<?php
/**
 * @see https://github.com/WordPress/gutenberg/blob/trunk/docs/reference-guides/block-api/block-metadata.md#render
 */
?>
<div id="protohaven-events" data-img-size="<?php echo($attributes['imgSize']); ?>">
	<script type="text/json">
	<?php
	// We make the initial call to ph_neon_events here so that the page renders
	// with content. This is good for SEO.
	// If number of events exceeds pageSize, the remaining pages are fetched
	// client-side via JS (see lib.js `fetch_remaining_events`)
	//
	// The initial results fetched here do not include volatile data (e.g. seats
	// remaining) so it's fine to cache at 24h. The biggest impact of caching here
	// is that new classes may take up to 24h to appear, but those schedule enough
	// in advance that it shouldn't matter.
	$CACHE_ID = "ph_events_data";
	$result = wp_cache_get($CACHE_ID);
	if ( false === $result || $result[1] < (time() - (60*60*24)) ) {
		$result = array(json_encode(ph_neon_events_internal([
						'endDateAfter' => date('Y-m-d'),
						'publishedEvent' => true,
			'archived' => false,
			'pageSize' => 200,
		])), time());
		wp_cache_set($CACHE_ID, $result );
	}
	echo $result[0];
	?>
	</script>
</div>
