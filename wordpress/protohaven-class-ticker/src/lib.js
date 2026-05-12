function shorten_class_name(name) {
	let sp = name.substring(name.indexOf(":") + 1).trim();
	sp = sp[1].split('(')[0].trim();
	if (sp.length > 32) {
		return sp.substring(0, 32) + '...';
	}
	return sp;
}

export function ph_events_to_elems(evts) {
	let result = [];
	for (let e of evts) {
		if (!e.name) {
			continue
		}
		let seats = "";
		if (e.seats_left == 2) {
			seats = " 2 seats left!";
		} else if (e.seats_left == 1) {
			seats = " 1 seat left!";
		}
		result.push(<a key={e.url} href={e.url} target="_blank">
			<span style={{'display': 'inline-block', 'marginRight': '5px'}}>{shorten_class_name(e.name)}</span>
			<span style={{'display': 'inline-block'}}>({e.date}{seats})</span>
		</a>);
	}
	return result;
}
