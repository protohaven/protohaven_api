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
	$base = $attributes['base'];
	$table = $attributes['table'];
	$CACHE_ID = "protohaven_airtable_grid_" . $base . "_" . $table;
	$result = wp_cache_get($CACHE_ID);
	// Image links in Airtable have a 2hr TTL, so we have to cache less than this as long
	// as we're using Airtable as a source of truth for images.
	if ($result[1] < (time() - 3600) || !is_array($result[0]) || !array_key_exists('records', $result[0]) || count($result[0]['records']) === 0) {
		$result = array(
			do_airtable_fetch($attributes['token'], $base, $table),
			time()
		);
		wp_cache_set($CACHE_ID, $result);
	}
	echo json_encode($result[0]);
	?></script>
</div>
<div style="display: none;">
cached <?php echo $result[1]; ?><br/>
is_array <?php echo is_array($result[0]); ?><br/>
has_records <?php echo array_key_exists('records', $result[0]); ?><br/>
count <?php echo count($result[0]['records']); ?><br/>
</div>
