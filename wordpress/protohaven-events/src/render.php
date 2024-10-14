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
	echo json_encode(ph_neon_events_internal([
        	'endDateAfter' => date('Y-m-d'),
        	'publishedEvent' => true,
		'archived' => false,
		'pageSize' => 200,
	]));
	?>
	</script>
</div>
