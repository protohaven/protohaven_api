export function render_grid(data, {
	imgSize, titleField, subtitleField, imgField, bodyField, refField, refText
}) {
	let grid = [];
	for (let row of data) {
		let img = (row.fields[imgField] || [])[0];
		if (!img) {
			console.warn("Skipping no-img row", row, "lacking field", imgField);
			continue;
		}
		let title = row.fields[titleField];
		let subtitle = row.fields[subtitleField];
		let body = row.fields[bodyField] || null;
		let ref = row.fields[refField];
		grid.push(<div key={row.id} style={{ minWidth: imgSize, maxWidth: '308px', }}>
			<p>
				<img src={img['thumbnails']['large']['url']} style={{maxWidth: imgSize, maxHeight: imgSize, marginLeft: 'auto', marginRight: 'auto'}}/>
			</p>
			<p className="has-text-align-center">
				{title && <strong>{title}</strong>}
				{title && subtitle && <br/>}
				{subtitle && <em>{subtitle}</em>}
			</p>
			{body && <p className="has-text-align-center">{body}</p>}
			{ref && <p className="has-text-align-center"><a href={ref} target="_blank">{refText}</a></p>}
		</div>);
	}

	return (
		<div style={{
			display: 'grid',
			gridTemplateColumns: `repeat(auto-fill, minmax(${imgSize}, 1fr))`,
			justifyItems: 'center',
			alignItems: 'top',
			gap: '10px',
			}}>
			{grid}
		</div>
	);
}
