function shorten_class_name(name) {
	return name.split(':')[1].split('(')[0];
}

export function ph_events_to_elems(evts) {
	let result = [];
	for (let e of evts) {
		let seats = "";
		if (e.seats_left == 2) {
			seats = " 2 seats left!";
		} else if (e.seats_left == 1) {
			seats = " 1 seat left!";
		}
		let fmt = `${shorten_class_name(e.name)} (${e.date}${seats})`;
		result.push(<a key={e.url} href={e.url} target="_blank">{fmt}</a>);
	}
	return result;
}
