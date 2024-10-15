export function get_ph_data(token, base, table) {
	console.log("Getting data using token", token, "base", base, "table", table);
	return fetch(`https://api.airtable.com/v0/${base}/${table}`, {
		headers: {Authorization: `Bearer ${token}`},
	}).then((rep) => {
		if (rep.status != 200) {
			throw Error(rep.status_text);
		}
		return rep.json().then(data => data['records'] || []);
	});
};

export function render_grid(data, {
	imgSize, numColumns, titleField, subtitleField, imgField, bodyField, refField, refText
}) {
	let grid = [];
	for (let row of data) {
		let header = [];
		let title = row.fields[titleField];
		if (title) {
			header.push(<strong>{title}</strong>, <br/>);
		}
		let subtitle = row.fields[subtitleField];
		if (subtitle) {
			header.push(<em>{subtitle}</em>, <br/>);
		}
		if (header.length > 0) {
			header.pop();
			header = <p class="has-text-align-center">{header}</p>;
		} else {
			header = null;
		}

		let img = (row.fields[imgField] || [])[0];
		if (!img) {
			continue;
		}
		img = (<p>
			<img
				src={img['thumbnails']['large']['url']}
				style={{maxWidth: imgSize, maxHeight: imgSize, marginLeft: 'auto', marginRight: 'auto'}}
				/>
			</p>);

		let body = row.fields[bodyField] || null;
		if (body) {
			body = <p class="has-text-align-center">{body}</p>;
		}
		let ref = row.fields[refField];
		if (ref) {
			ref = (<p class="has-text-align-center"><a href={ref} target="_blank">{refText}</a></p>);
		}

		grid.push([img, header, body, ref]);
	}

	let numCol = Math.max(1, parseInt(numColumns)); // Prevent columns ever reaching 0 or negative and causing infinite loop
	return (
		<div style={{
			display: 'grid',
			gridTemplateColumns: `repeat(auto-fill, minmax(${imgSize}, 1fr))`,
			justifyItems: 'center',
			alignItems: 'top',
			gap: '10px',
			}}>
		  {grid.map(item => (
		    <div style={{ minWidth: imgSize, maxWidth: '308px', }}>{item}</div>
		  ))}
		</div>
	);
}
