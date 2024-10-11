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
		result.push(<a href={e.url} target="_blank">{fmt}</a>);
	}
	return result;
}

export function get_ph_events() {
	return fetch("https://staging.api.protohaven.org/event_ticker").then((rep) => {
		if (rep.status != 200) {
			throw Error(rep.status_text);
		}
		return rep.json();
	});
};
